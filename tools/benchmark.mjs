import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { performance } from "node:perf_hooks";

import { compactPostToolUsePayload, createDefaultOptions } from "../src/token-vault-core.mjs";

const scenarios = [
  {
    name: "large test log with failures",
    response: {
      exit_code: 1,
      stdout: Array.from({ length: 2500 }, (_, i) => i % 333 === 0
        ? `${i + 1}: ERROR assertion failed in test_${i}`
        : `${i + 1}: PASS ${"detail ".repeat(12)}`).join("\n"),
      stderr: "warning: deprecated API used\n",
    },
  },
  {
    name: "repo-wide search output",
    response: Array.from({ length: 1800 }, (_, i) => `src/module_${i % 40}/file_${i}.ts:${i}: const value${i} = "${"x".repeat(40)}";`).join("\n"),
  },
  {
    name: "small command output",
    response: "git status clean\n",
  },
];

function bytes(value) {
  return Buffer.byteLength(typeof value === "string" ? value : JSON.stringify(value), "utf8");
}

const root = await mkdtemp(join(tmpdir(), "codex-token-vault-bench-"));
try {
  const rows = [];
  for (const scenario of scenarios) {
    const payload = {
      hook_event_name: "PostToolUse",
      tool_name: "functions.shell_command",
      tool_use_id: `bench-${scenario.name}`,
      cwd: process.cwd(),
      tool_input: { command: scenario.name },
      tool_response: scenario.response,
    };
    const rawBytes = bytes(payload.tool_response);
    const start = performance.now();
    const result = await compactPostToolUsePayload(payload, createDefaultOptions({
      root,
      thresholdBytes: 12_000,
      maxSummaryChars: 4_000,
    }));
    const elapsedMs = performance.now() - start;
    const compactBytes = result ? Buffer.byteLength(result.text, "utf8") : rawBytes;
    rows.push({
      scenario: scenario.name,
      raw_bytes: rawBytes,
      applied_bytes: compactBytes,
      reduction_pct: Number((100 * (1 - compactBytes / rawBytes)).toFixed(1)),
      hook_ms: Number(elapsedMs.toFixed(2)),
      compacted: Boolean(result),
    });
  }
  console.table(rows);
  console.log(JSON.stringify({ vault_root: root, rows }, null, 2));
} finally {
  await rm(root, { recursive: true, force: true });
}
