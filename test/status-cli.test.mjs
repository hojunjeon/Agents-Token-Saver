import assert from "node:assert/strict";
import { mkdir, mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { spawnSync } from "node:child_process";
import test from "node:test";

async function withTempCodexHome(fn) {
  const root = await mkdtemp(join(tmpdir(), "codex-status-cli-test-"));
  try {
    return await fn(root);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
}

test("status cli prints concise Korean quota lines", async () => {
  await withTempCodexHome(async (codexHome) => {
    const dir = join(codexHome, "sessions", "2026", "05", "24");
    await mkdir(dir, { recursive: true });
    await writeFile(
      join(dir, "rollout-test.jsonl"),
      `${JSON.stringify({ timestamp: "2026-05-24T02:00:00.000Z", type: "event_msg", payload: { type: "token_count", rate_limits: { primary: { used_percent: 12, window_minutes: 300, resets_at: 1779617141 }, secondary: { used_percent: 11, window_minutes: 10080, resets_at: 1780185722 }, plan_type: "prolite" } } })}\n`,
      "utf8",
    );

    const run = spawnSync(process.execPath, ["src/codex-status-cli.mjs"], {
      encoding: "utf8",
      env: { ...process.env, CODEX_HOME: codexHome },
    });

    assert.equal(run.status, 0);
    assert.match(run.stdout, /5시간 한도: 12%/);
    assert.match(run.stdout, /주간 한도: 11%/);
    assert.match(run.stdout, /플랜: prolite/);
  });
});
