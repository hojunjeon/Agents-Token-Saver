import assert from "node:assert/strict";
import { mkdir, mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import {
  buildStatusAdditionalContext,
  findLatestTokenStatus,
  isStatusPrompt,
} from "../src/codex-status-core.mjs";

async function withTempCodexHome(fn) {
  const root = await mkdtemp(join(tmpdir(), "codex-status-test-"));
  try {
    return await fn(root);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
}

test("isStatusPrompt matches desktop status slash commands only", () => {
  assert.equal(isStatusPrompt("/상태"), true);
  assert.equal(isStatusPrompt(" /상태 "), true);
  assert.equal(isStatusPrompt("/status"), true);
  assert.equal(isStatusPrompt("/??"), true);
  assert.equal(isStatusPrompt("상태 왜 안 돼"), false);
  assert.equal(isStatusPrompt("fix /status rendering"), false);
});

test("findLatestTokenStatus reads latest token_count rate limits", async () => {
  await withTempCodexHome(async (codexHome) => {
    const dir = join(codexHome, "sessions", "2026", "05", "24");
    await mkdir(dir, { recursive: true });
    const file = join(dir, "rollout-test.jsonl");
    await writeFile(
      file,
      [
        JSON.stringify({ timestamp: "2026-05-24T01:00:00.000Z", type: "event_msg", payload: { type: "token_count", rate_limits: { primary: { used_percent: 4, window_minutes: 300, resets_at: 1779610000 }, secondary: { used_percent: 7, window_minutes: 10080, resets_at: 1780180000 } } } }),
        JSON.stringify({ timestamp: "2026-05-24T02:00:00.000Z", type: "event_msg", payload: { type: "token_count", rate_limits: { primary: { used_percent: 12, window_minutes: 300, resets_at: 1779617141 }, secondary: { used_percent: 11, window_minutes: 10080, resets_at: 1780185722 }, plan_type: "prolite" } } }),
      ].join("\n"),
      "utf8",
    );

    const status = await findLatestTokenStatus({ codexHome, now: new Date("2026-05-24T06:00:00.000Z") });

    assert.equal(status.primary.usedPercent, 12);
    assert.equal(status.secondary.usedPercent, 11);
    assert.equal(status.planType, "prolite");
    assert.equal(status.primary.resetAtKst, "2026-05-24 19:05:41 KST");
    assert.equal(status.secondary.resetAtKst, "2026-05-31 09:02:02 KST");
  });
});

test("buildStatusAdditionalContext tells the model to answer the status directly", async () => {
  await withTempCodexHome(async (codexHome) => {
    const dir = join(codexHome, "sessions", "2026", "05", "24");
    await mkdir(dir, { recursive: true });
    await writeFile(
      join(dir, "rollout-test.jsonl"),
      `${JSON.stringify({ timestamp: "2026-05-24T02:00:00.000Z", type: "event_msg", payload: { type: "token_count", rate_limits: { primary: { used_percent: 12, window_minutes: 300, resets_at: 1779617141 }, secondary: { used_percent: 11, window_minutes: 10080, resets_at: 1780185722 } } } })}\n`,
      "utf8",
    );

    const context = await buildStatusAdditionalContext({ prompt: "/상태", codexHome });

    assert.match(context, /5시간 한도: 12%/);
    assert.match(context, /주간 한도: 11%/);
    assert.match(context, /2026-05-24 19:05:41 KST/);
    assert.match(context, /이 상태 정보만 간결하게 답변/);
  });
});
