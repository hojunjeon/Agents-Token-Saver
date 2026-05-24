#!/usr/bin/env node
import { mkdir, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { stdin, stdout } from "node:process";

import { compactPostToolUsePayload, createDefaultOptions } from "./token-vault-core.mjs";

async function readStdin() {
  const chunks = [];
  for await (const chunk of stdin) chunks.push(chunk);
  return Buffer.concat(chunks).toString("utf8");
}

async function logError(root, error) {
  try {
    await mkdir(root, { recursive: true });
    await writeFile(
      join(root, "hook-errors.jsonl"),
      JSON.stringify({ at: new Date().toISOString(), error: String(error?.stack || error) }) + "\n",
      { encoding: "utf8", flag: "a" },
    );
  } catch {
    // Fail open: never break Codex tool execution because logging failed.
  }
}

async function main() {
  const options = createDefaultOptions();
  try {
    const input = await readStdin();
    const payload = input.trim() ? JSON.parse(input) : {};
    const result = await compactPostToolUsePayload(payload, options);
    if (!result) return;
    stdout.write(JSON.stringify({
      continue: false,
      stopReason: result.text,
      hookSpecificOutput: {
        hookEventName: "PostToolUse",
        additionalContext: result.text,
      },
    }));
  } catch (error) {
    await logError(options.root, error);
  }
}

main();
