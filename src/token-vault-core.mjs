import { createHash } from "node:crypto";
import { mkdir, writeFile, appendFile } from "node:fs/promises";
import { join, resolve } from "node:path";

const DEFAULT_THRESHOLD_BYTES = 12_000;
const DEFAULT_MAX_SUMMARY_CHARS = 4_000;
const MAX_SIGNAL_LINES = 80;
const SIGNAL_RE = /(error|exception|traceback|failed|failure|warning|warn|critical|fatal|denied|timeout|timed out|not found|no such file|assert|panic|segfault|econnreset|epipe)/i;
const SECRET_KEY_RE = /authorization|token|secret|password|api[_-]?key|cookie|signature|private[_-]?key/i;

export function createDefaultOptions(overrides = {}) {
  const home = process.env.USERPROFILE || process.env.HOME || process.cwd();
  const root = overrides.root
    ?? process.env.CODEX_TOKEN_VAULT_DIR
    ?? process.env.OMX_TOKEN_VAULT_DIR
    ?? join(home, ".omx", "token-vault-codex");
  return {
    root,
    thresholdBytes: positiveInt(overrides.thresholdBytes ?? process.env.CODEX_TOKEN_VAULT_THRESHOLD, DEFAULT_THRESHOLD_BYTES),
    maxSummaryChars: positiveInt(overrides.maxSummaryChars ?? process.env.CODEX_TOKEN_VAULT_MAX_CHARS, DEFAULT_MAX_SUMMARY_CHARS),
    enabled: parseEnabled(overrides.enabled ?? process.env.CODEX_TOKEN_VAULT ?? process.env.OMX_TOKEN_VAULT ?? "1"),
  };
}

function positiveInt(value, fallback) {
  const parsed = Number.parseInt(String(value ?? ""), 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

function parseEnabled(value) {
  return !new Set(["0", "false", "no", "off"]).has(String(value).trim().toLowerCase());
}

function byteLen(text) {
  return Buffer.byteLength(String(text), "utf8");
}

function stableId(parts) {
  const h = createHash("sha256");
  for (const part of parts) {
    h.update(String(part ?? ""), "utf8");
    h.update("\0");
  }
  return h.digest("hex").slice(0, 16);
}

function safeJson(value) {
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

function rawResponseText(value) {
  return typeof value === "string" ? value : safeJson(value);
}

function hasVaultArtifactPath(value, root) {
  const haystack = JSON.stringify(value ?? "");
  const normalizePathText = (text) => text.replace(/\\+/g, "/").replace(/\/+/g, "/").toLowerCase();
  const normalizedRoot = normalizePathText(root);
  const normalizedHaystack = normalizePathText(haystack);
  return normalizedHaystack.includes("/.omx/token-vault")
    || normalizedHaystack.includes("/.omx/token-vault-codex")
    || normalizedHaystack.includes(`${normalizedRoot}/artifacts`);
}

function redact(value, keyHint = "") {
  if (SECRET_KEY_RE.test(keyHint)) return "[REDACTED]";
  if (typeof value === "string") {
    return value
      .replace(/Bearer\s+[A-Za-z0-9._~+/=-]+/g, "Bearer [REDACTED]")
      .replace(/(sk-[A-Za-z0-9_-]{12,})/g, "[REDACTED]");
  }
  if (Array.isArray(value)) return value.map((item) => redact(item, keyHint));
  if (value && typeof value === "object") {
    const out = {};
    for (const [key, child] of Object.entries(value)) {
      out[key] = redact(child, key);
    }
    return out;
  }
  return value;
}

export function redactedSummaryText(value) {
  return safeJson(redact(value));
}

function lineSample(text, budget) {
  const lines = String(text).split(/\r?\n/);
  if (lines.length === 1) {
    return {
      line_count: text ? 1 : 0,
      excerpt: redact(String(text).slice(0, budget)),
    };
  }
  const headN = Math.min(40, Math.max(8, Math.floor(budget / 150)));
  const tailN = Math.min(40, Math.max(8, Math.floor(budget / 180)));
  const signal = [];
  lines.forEach((line, idx) => {
    if (signal.length < MAX_SIGNAL_LINES && SIGNAL_RE.test(line)) {
      signal.push(`${idx + 1}: ${redact(line.slice(0, 260))}`);
    }
  });
  const head = lines.slice(0, headN).map((line, idx) => `${idx + 1}: ${redact(line.slice(0, 260))}`);
  const tailStart = Math.max(lines.length - tailN, headN);
  const tail = lines.slice(tailStart).map((line, idx) => `${tailStart + idx + 1}: ${redact(line.slice(0, 260))}`);
  return {
    line_count: lines.length,
    head,
    signal_lines: signal,
    tail,
    omitted_lines: Math.max(0, lines.length - head.length - tail.length),
  };
}

function compactValue(value, budget, depth = 0, keyHint = "") {
  if (depth > 5) return "<max-depth elided>";
  if (SECRET_KEY_RE.test(keyHint)) return "[REDACTED]";
  if (typeof value === "string") {
    if (value.length <= budget) return redact(value);
    return {
      ...lineSample(value, Math.max(600, budget)),
      original_chars: value.length,
      truncated: true,
    };
  }
  if (Array.isArray(value)) {
    if (value.length <= 40) {
      const childBudget = Math.max(500, Math.floor(budget / Math.max(1, value.length)));
      return value.map((item) => compactValue(item, childBudget, depth + 1, keyHint));
    }
    return {
      items_head: value.slice(0, 25).map((item) => compactValue(item, 700, depth + 1, keyHint)),
      items_tail: value.slice(-10).map((item) => compactValue(item, 700, depth + 1, keyHint)),
      omitted_items: value.length - 35,
      total_items: value.length,
    };
  }
  if (value && typeof value === "object") {
    const out = {};
    const priority = ["success", "status", "exit_code", "exitCode", "code", "error", "message", "stderr", "stdout", "duration", "duration_ms", "total_lines", "total_count", "file_size", "truncated", "hint"];
    for (const key of priority) {
      if (Object.prototype.hasOwnProperty.call(value, key)) {
        out[key] = compactValue(value[key], key === "stdout" || key === "stderr" ? 2200 : 1600, depth + 1, key);
      }
    }
    for (const [key, val] of Object.entries(value)) {
      if (Object.prototype.hasOwnProperty.call(out, key)) continue;
      if (Object.keys(out).length >= 28) {
        out._omitted_keys = (out._omitted_keys || 0) + 1;
        continue;
      }
      const childBudget = ["output", "content", "matches", "files", "messages", "tool_response"].includes(key) ? 2600 : 900;
      out[key] = compactValue(val, childBudget, depth + 1, key);
    }
    return out;
  }
  return value;
}

function parseMaybeJson(text) {
  const trimmed = String(text || "").trim();
  if (!trimmed) return null;
  try {
    return JSON.parse(trimmed);
  } catch {
    return null;
  }
}

async function tryWriteSqlite(root, row) {
  try {
    const sqlite = await import("node:sqlite");
    const dbPath = join(root, "vault.sqlite");
    const db = new sqlite.DatabaseSync(dbPath);
    try {
      db.exec("CREATE TABLE IF NOT EXISTS tool_results (id TEXT PRIMARY KEY, stored_at TEXT, tool_name TEXT, cwd TEXT, command TEXT, original_bytes INTEGER, artifact_path TEXT, payload_json TEXT)");
      const stmt = db.prepare("INSERT OR REPLACE INTO tool_results VALUES (?, ?, ?, ?, ?, ?, ?, ?)");
      stmt.run(row.id, row.stored_at, row.tool_name, row.cwd, row.command, row.original_bytes, row.artifact_path, row.payload_json);
    } finally {
      db.close();
    }
  } catch {
    await appendFile(join(root, "index.jsonl"), JSON.stringify(row) + "\n", "utf8");
  }
}

async function storeArtifact({ root, id, payload, raw, originalBytes }) {
  const artifactDir = join(root, "artifacts");
  await mkdir(artifactDir, { recursive: true });
  const artifactPath = resolve(join(artifactDir, `${id}.json`));
  const artifact = {
    id,
    stored_at: new Date().toISOString(),
    hook: "PostToolUse",
    tool_name: payload.tool_name ?? null,
    tool_use_id: payload.tool_use_id ?? null,
    cwd: payload.cwd ?? null,
    command: payload?.tool_input?.command ?? null,
    original_bytes: originalBytes,
    tool_input: payload.tool_input ?? null,
    tool_response: payload.tool_response ?? null,
    tool_response_text: raw,
  };
  const payloadJson = JSON.stringify(artifact, null, 2);
  await writeFile(artifactPath, payloadJson, "utf8");
  await tryWriteSqlite(root, {
    id,
    stored_at: artifact.stored_at,
    tool_name: artifact.tool_name,
    cwd: artifact.cwd,
    command: artifact.command,
    original_bytes: originalBytes,
    artifact_path: artifactPath,
    payload_json: payloadJson,
  });
  return artifactPath;
}

export async function compactPostToolUsePayload(payload, options = createDefaultOptions()) {
  if (!options.enabled) return null;
  const eventName = payload.hook_event_name ?? payload.hookEventName;
  if (eventName !== "PostToolUse") return null;
  if (hasVaultArtifactPath(payload.tool_input, options.root) || hasVaultArtifactPath(payload.tool_response, options.root)) return null;

  const raw = rawResponseText(payload.tool_response);
  const originalBytes = byteLen(raw);
  if (originalBytes < options.thresholdBytes) return null;

  const id = stableId([payload.tool_name || "tool", payload.tool_use_id || "", raw]);
  const artifactPath = await storeArtifact({ root: options.root, id, payload, raw, originalBytes });
  const parsed = typeof payload.tool_response === "string" ? parseMaybeJson(payload.tool_response) : payload.tool_response;
  const compactResult = compactValue(parsed ?? raw, options.maxSummaryChars);
  const wrapper = {
    _codex_token_vault: {
      id,
      full_result_path: artifactPath,
      original_bytes: originalBytes,
      policy: "loss-aware compaction: exact full PostToolUse payload stored outside model context; compact summary preserves status, head/tail, and high-signal lines",
      retrieve: "Read full_result_path directly for exact original output. Vault artifact reads are bypassed to avoid recursive compaction.",
    },
    tool_name: payload.tool_name ?? null,
    compact_result: compactResult,
  };

  let text = JSON.stringify(wrapper, null, 2);
  for (let i = 0; i < 3; i += 1) {
    wrapper._codex_token_vault.compact_bytes = byteLen(text);
    wrapper._codex_token_vault.reduction_pct = Number((100 * (1 - wrapper._codex_token_vault.compact_bytes / originalBytes)).toFixed(1));
    const next = JSON.stringify(wrapper, null, 2);
    if (byteLen(next) === wrapper._codex_token_vault.compact_bytes) {
      text = next;
      break;
    }
    text = next;
  }
  wrapper._codex_token_vault.compact_bytes = byteLen(text);
  wrapper._codex_token_vault.reduction_pct = Number((100 * (1 - wrapper._codex_token_vault.compact_bytes / originalBytes)).toFixed(1));
  text = JSON.stringify(wrapper, null, 2);
  if (byteLen(text) >= originalBytes * 0.85) return null;
  return { text, wrapper };
}
