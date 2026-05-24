import assert from "node:assert/strict";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { spawnSync } from "node:child_process";
import test from "node:test";

async function withTempVault(fn) {
  const root = await mkdtemp(join(tmpdir(), "codex-token-vault-cli-test-"));
  try {
    return await fn(root);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
}

test("hook cli emits Codex PostToolUse replacement output for large payloads", async () => {
  await withTempVault(async (root) => {
    const payload = {
      hook_event_name: "PostToolUse",
      tool_name: "functions.shell_command",
      tool_response: "line\n".repeat(5000),
    };

    const run = spawnSync(process.execPath, ["src/codex-token-vault-hook.mjs"], {
      input: JSON.stringify(payload),
      encoding: "utf8",
      env: {
        ...process.env,
        CODEX_TOKEN_VAULT_DIR: root,
        CODEX_TOKEN_VAULT_THRESHOLD: "1000",
      },
    });

    assert.equal(run.status, 0);
    const output = JSON.parse(run.stdout);
    assert.equal(output.continue, false);
    assert.match(output.stopReason, /_codex_token_vault/);
    assert.equal(output.hookSpecificOutput.hookEventName, "PostToolUse");
  });
});
