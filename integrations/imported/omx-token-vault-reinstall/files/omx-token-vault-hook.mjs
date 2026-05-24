#!/usr/bin/env node
import { createHash } from 'node:crypto';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';

const DEFAULT_THRESHOLD = 12_000;
const DEFAULT_MAX_CHARS = 4_000;
const MAX_SIGNAL_LINES = 80;
const SIGNAL_RE = /(error|exception|traceback|failed|failure|warning|warn|critical|fatal|denied|timeout|timed out|not found|no such file|assert|panic|segfault|econnreset|epipe)/i;
const ROOT = process.env.OMX_TOKEN_VAULT_DIR || '/home/ubuntu/.omx/token-vault';
const ARTIFACT_DIR = `${ROOT}/artifacts`;
const INDEX_PATH = `${ROOT}/index.jsonl`;

function enabled() {
  return !new Set(['0', 'false', 'no', 'off']).has(String(process.env.OMX_TOKEN_VAULT || '1').trim().toLowerCase());
}
function intEnv(name, fallback) {
  const parsed = Number.parseInt(String(process.env[name] || ''), 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}
function byteLen(text) { return Buffer.byteLength(text, 'utf8'); }
function stableId(parts) {
  const h = createHash('sha256');
  for (const part of parts) { h.update(String(part ?? ''), 'utf8'); h.update('\0'); }
  return h.digest('hex').slice(0, 16);
}
function safeJson(value) {
  try { return JSON.stringify(value, null, 2); } catch { return String(value); }
}
function rawResponseText(value) {
  if (typeof value === 'string') return value;
  return safeJson(value);
}
function hasVaultArtifactPath(value) {
  return JSON.stringify(value ?? '').includes('/.omx/token-vault/artifacts/');
}
function lineSample(text, budget) {
  const lines = text.split(/\r?\n/);
  if (lines.length === 1) return { line_count: text ? 1 : 0, excerpt: text.slice(0, budget) };
  const headN = Math.min(40, Math.max(10, Math.floor(budget / 140)));
  const tailN = Math.min(40, Math.max(10, Math.floor(budget / 160)));
  const signal = [];
  lines.forEach((line, idx) => {
    if (signal.length < MAX_SIGNAL_LINES && SIGNAL_RE.test(line)) signal.push(`${idx + 1}: ${line.slice(0, 240)}`);
  });
  const head = lines.slice(0, headN).map((line, idx) => `${idx + 1}: ${line.slice(0, 240)}`);
  const tailStart = Math.max(lines.length - tailN, headN);
  const tail = lines.slice(tailStart).map((line, idx) => `${tailStart + idx + 1}: ${line.slice(0, 240)}`);
  return { line_count: lines.length, head, signal_lines: signal, tail, omitted_lines: Math.max(0, lines.length - head.length - tail.length) };
}
function compactValue(value, budget, depth = 0) {
  if (depth > 5) return '<max-depth elided>';
  if (typeof value === 'string') {
    if (value.length <= budget) return value;
    return { ...lineSample(value, Math.max(600, budget)), original_chars: value.length, truncated: true };
  }
  if (Array.isArray(value)) {
    if (value.length <= 40) return value.map((item) => compactValue(item, Math.max(500, Math.floor(budget / Math.max(1, value.length))), depth + 1));
    return {
      items_head: value.slice(0, 25).map((item) => compactValue(item, 700, depth + 1)),
      items_tail: value.slice(-10).map((item) => compactValue(item, 700, depth + 1)),
      omitted_items: value.length - 35,
      total_items: value.length,
    };
  }
  if (value && typeof value === 'object') {
    const out = {};
    const priority = ['success', 'status', 'exit_code', 'exitCode', 'code', 'error', 'message', 'stderr', 'stdout', 'duration', 'duration_ms', 'total_lines', 'total_count', 'file_size', 'truncated', 'hint'];
    for (const key of priority) if (Object.prototype.hasOwnProperty.call(value, key)) out[key] = compactValue(value[key], key === 'stdout' || key === 'stderr' ? 2200 : 1600, depth + 1);
    for (const [key, val] of Object.entries(value)) {
      if (Object.prototype.hasOwnProperty.call(out, key)) continue;
      if (Object.keys(out).length >= 28) { out._omitted_keys = (out._omitted_keys || 0) + 1; continue; }
      const childBudget = ['output', 'content', 'matches', 'files', 'messages', 'tool_response'].includes(key) ? 2600 : 900;
      out[key] = compactValue(val, childBudget, depth + 1);
    }
    return out;
  }
  return value;
}
function parseMaybeJson(text) {
  const trimmed = String(text || '').trim();
  if (!trimmed) return null;
  try { return JSON.parse(trimmed); } catch { return null; }
}
function storeArtifact({ id, payload, raw, originalBytes }) {
  mkdirSync(ARTIFACT_DIR, { recursive: true });
  const artifactPath = `${ARTIFACT_DIR}/${id}.json`;
  const artifact = {
    id,
    stored_at: new Date().toISOString(),
    hook: 'PostToolUse',
    tool_name: payload.tool_name ?? null,
    tool_use_id: payload.tool_use_id ?? null,
    cwd: payload.cwd ?? null,
    command: payload?.tool_input?.command ?? null,
    original_bytes: originalBytes,
    tool_input: payload.tool_input ?? null,
    tool_response: payload.tool_response ?? null,
    tool_response_text: raw,
  };
  writeFileSync(artifactPath, JSON.stringify(artifact, null, 2), 'utf8');
  const index = {
    id,
    stored_at: artifact.stored_at,
    tool_name: artifact.tool_name,
    artifact_path: artifactPath,
    original_bytes: originalBytes,
    cwd: artifact.cwd,
    command: artifact.command,
  };
  writeFileSync(INDEX_PATH, JSON.stringify(index) + '\n', { encoding: 'utf8', flag: 'a' });
  return artifactPath;
}
function compact(payload) {
  const threshold = intEnv('OMX_TOKEN_VAULT_THRESHOLD', DEFAULT_THRESHOLD);
  const maxChars = intEnv('OMX_TOKEN_VAULT_MAX_CHARS', DEFAULT_MAX_CHARS);
  if (!enabled()) return null;
  if (payload.hook_event_name !== 'PostToolUse' && payload.hookEventName !== 'PostToolUse') return null;
  if (hasVaultArtifactPath(payload.tool_input) || hasVaultArtifactPath(payload.tool_response)) return null;
  const raw = rawResponseText(payload.tool_response);
  const originalBytes = byteLen(raw);
  if (originalBytes < threshold) return null;
  const id = stableId([payload.tool_name || 'tool', payload.tool_use_id || '', raw]);
  const artifactPath = storeArtifact({ id, payload, raw, originalBytes });
  const parsed = typeof payload.tool_response === 'string' ? parseMaybeJson(payload.tool_response) : payload.tool_response;
  const responseForCompact = parsed ?? raw;
  const compactResult = compactValue(responseForCompact, maxChars);
  const wrapper = {
    _omx_token_vault: {
      id,
      full_result_path: artifactPath,
      original_bytes: originalBytes,
      policy: 'fail-open loss-aware compaction: exact full PostToolUse payload stored outside model context; head/tail and high-signal lines preserved',
      retrieve: 'Read full_result_path directly (for example: sed -n "1,220p" <path> or jq .tool_response_text <path>) for exact original output. Vault artifact reads are not compacted.',
    },
    tool_name: payload.tool_name ?? null,
    compact_result: compactResult,
  };
  let text = JSON.stringify(wrapper, null, 2);
  // Stabilize metadata after adding byte-count fields, because those fields change the wrapper size.
  for (let i = 0; i < 3; i += 1) {
    const compactBytes = byteLen(text);
    wrapper._omx_token_vault.compact_bytes = compactBytes;
    wrapper._omx_token_vault.reduction_pct = Number((100 * (1 - compactBytes / originalBytes)).toFixed(1));
    const next = JSON.stringify(wrapper, null, 2);
    if (byteLen(next) === compactBytes) { text = next; break; }
    text = next;
  }
  wrapper._omx_token_vault.compact_bytes = byteLen(text);
  wrapper._omx_token_vault.reduction_pct = Number((100 * (1 - wrapper._omx_token_vault.compact_bytes / originalBytes)).toFixed(1));
  text = JSON.stringify(wrapper, null, 2);
  if (byteLen(text) >= originalBytes * 0.85) return null;
  return { text, wrapper };
}
function main() {
  try {
    const input = readFileSync(0, 'utf8');
    const payload = input.trim() ? JSON.parse(input) : {};
    const result = compact(payload);
    if (!result) return;
    // PostToolUse supports continue:false; Codex replaces the original tool result with this feedback/stop text.
    process.stdout.write(JSON.stringify({
      continue: false,
      stopReason: result.text,
      hookSpecificOutput: {
        hookEventName: 'PostToolUse',
        additionalContext: result.text,
      },
    }));
  } catch (err) {
    try {
      mkdirSync(ROOT, { recursive: true });
      writeFileSync(`${ROOT}/hook-errors.jsonl`, JSON.stringify({ at: new Date().toISOString(), error: String(err?.stack || err) }) + '\n', { flag: 'a' });
    } catch {}
    // Fail open: no stdout, exit 0, original tool result proceeds.
  }
}
main();
