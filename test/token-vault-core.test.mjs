import assert from "node:assert/strict";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import {
  compactPostToolUsePayload,
  createDefaultOptions,
  redactedSummaryText,
} from "../src/token-vault-core.mjs";

async function withTempVault(fn) {
  const root = await mkdtemp(join(tmpdir(), "codex-token-vault-test-"));
  try {
    return await fn(root);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
}

test("passes through small PostToolUse payloads", async () => {
  await withTempVault(async (root) => {
    const result = await compactPostToolUsePayload({
      hook_event_name: "PostToolUse",
      tool_name: "functions.shell_command",
      tool_response: "short output",
    }, createDefaultOptions({ root, thresholdBytes: 1000 }));

    assert.equal(result, null);
  });
});

test("stores large output and returns compact summary with retrieval path", async () => {
  await withTempVault(async (root) => {
    const raw = Array.from({ length: 500 }, (_, i) => {
      if (i === 250) return "ERROR: important failure signal";
      return `line ${i + 1}: ${"x".repeat(80)}`;
    }).join("\n");

    const result = await compactPostToolUsePayload({
      hook_event_name: "PostToolUse",
      tool_name: "functions.shell_command",
      tool_use_id: "call-1",
      cwd: "C:\\repo",
      tool_input: { command: "npm test" },
      tool_response: { exit_code: 1, stdout: raw, stderr: "warning: noisy stderr" },
    }, createDefaultOptions({ root, thresholdBytes: 1000, maxSummaryChars: 3000 }));

    assert.ok(result);
    assert.ok(result.text.length < raw.length * 0.5);
    assert.match(result.text, /_codex_token_vault/);
    assert.match(result.text, /full_result_path/);
    assert.match(result.text, /ERROR: important failure signal/);
    assert.match(result.text, /warning: noisy stderr/);

    const artifactPath = result.wrapper._codex_token_vault.full_result_path;
    const artifact = JSON.parse(await readFile(artifactPath, "utf8"));
    assert.equal(artifact.tool_name, "functions.shell_command");
    assert.equal(artifact.tool_input.command, "npm test");
    assert.equal(artifact.tool_response.stdout, raw);
  });
});

test("redacts common secret-shaped values from compact summaries", () => {
  const text = redactedSummaryText({
    authorization: "Bearer abc",
    api_key: "secret-value",
    nested: { password: "pw", safe: "visible" },
  });

  assert.doesNotMatch(text, /secret-value|Bearer abc|"pw"/);
  assert.match(text, /\[REDACTED\]/);
  assert.match(text, /visible/);
});

test("does not recursively compact vault artifact reads", async () => {
  await withTempVault(async (root) => {
    const result = await compactPostToolUsePayload({
      hook_event_name: "PostToolUse",
      tool_name: "functions.shell_command",
      tool_input: { command: `Get-Content ${root}\\artifacts\\abc.json` },
      tool_response: "x".repeat(50_000),
    }, createDefaultOptions({ root, thresholdBytes: 1000 }));

    assert.equal(result, null);
  });
});
