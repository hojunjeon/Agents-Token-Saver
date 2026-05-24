#!/usr/bin/env node
import { mkdir, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { stdin, stdout } from "node:process";

import { buildStatusAdditionalContext, getDefaultCodexHome } from "./codex-status-core.mjs";

async function readStdin() {
  const chunks = [];
  for await (const chunk of stdin) chunks.push(chunk);
  return Buffer.concat(chunks).toString("utf8");
}

async function logError(codexHome, error) {
  try {
    const dir = join(codexHome, "hooks");
    await mkdir(dir, { recursive: true });
    await writeFile(
      join(dir, "codex-status-hook-errors.jsonl"),
      JSON.stringify({ at: new Date().toISOString(), error: String(error?.stack || error) }) + "\n",
      { encoding: "utf8", flag: "a" },
    );
  } catch {
    // Fail open: status lookup must never block a prompt.
  }
}

function readPrompt(payload) {
  return payload?.prompt ?? payload?.user_prompt ?? payload?.message ?? "";
}

async function main() {
  const codexHome = getDefaultCodexHome();
  try {
    const input = await readStdin();
    const payload = input.trim() ? JSON.parse(input) : {};
    if (payload?.hook_event_name !== "UserPromptSubmit") return;

    const additionalContext = await buildStatusAdditionalContext({
      prompt: readPrompt(payload),
      codexHome,
    });
    if (!additionalContext) return;

    stdout.write(JSON.stringify({
      hookSpecificOutput: {
        hookEventName: "UserPromptSubmit",
        additionalContext,
      },
    }));
  } catch (error) {
    await logError(codexHome, error);
  }
}

main();
