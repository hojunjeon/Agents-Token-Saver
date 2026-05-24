import { readdir, readFile, stat } from "node:fs/promises";
import { homedir } from "node:os";
import { join } from "node:path";

const STATUS_PROMPTS = new Set(["/상태", "/status", "/??"]);

export function isStatusPrompt(prompt) {
  const normalized = String(prompt ?? "").trim().toLowerCase();
  return STATUS_PROMPTS.has(normalized);
}

export function getDefaultCodexHome() {
  return process.env.CODEX_HOME || join(homedir(), ".codex");
}

function formatKst(epochSeconds) {
  if (!Number.isFinite(epochSeconds)) return null;
  const date = new Date(epochSeconds * 1000);
  const parts = new Intl.DateTimeFormat("sv-SE", {
    timeZone: "Asia/Seoul",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(date);
  return `${parts.replace(" ", " ")} KST`;
}

async function collectJsonlFiles(root, limit = 80) {
  const files = [];

  async function walk(dir) {
    let entries;
    try {
      entries = await readdir(dir, { withFileTypes: true });
    } catch {
      return;
    }

    await Promise.all(entries.map(async (entry) => {
      const fullPath = join(dir, entry.name);
      if (entry.isDirectory()) {
        await walk(fullPath);
        return;
      }
      if (!entry.isFile() || !entry.name.endsWith(".jsonl")) return;
      try {
        const info = await stat(fullPath);
        files.push({ path: fullPath, mtimeMs: info.mtimeMs });
      } catch {
        // Ignore files disappearing while Codex writes session logs.
      }
    }));
  }

  await walk(join(root, "sessions"));
  return files.sort((a, b) => b.mtimeMs - a.mtimeMs).slice(0, limit);
}

function tokenStatusFromLine(line, sourcePath) {
  let event;
  try {
    event = JSON.parse(line);
  } catch {
    return null;
  }
  if (event?.type !== "event_msg" || event?.payload?.type !== "token_count") return null;
  const rateLimits = event.payload.rate_limits;
  const primary = rateLimits?.primary;
  const secondary = rateLimits?.secondary;
  if (!primary && !secondary) return null;

  return {
    timestamp: event.timestamp || null,
    sourcePath,
    planType: rateLimits?.plan_type || null,
    primary: {
      usedPercent: Number(primary?.used_percent),
      windowMinutes: Number(primary?.window_minutes),
      resetAt: Number(primary?.resets_at),
      resetAtKst: formatKst(Number(primary?.resets_at)),
    },
    secondary: {
      usedPercent: Number(secondary?.used_percent),
      windowMinutes: Number(secondary?.window_minutes),
      resetAt: Number(secondary?.resets_at),
      resetAtKst: formatKst(Number(secondary?.resets_at)),
    },
  };
}

export async function findLatestTokenStatus({ codexHome = getDefaultCodexHome() } = {}) {
  const files = await collectJsonlFiles(codexHome);
  let latest = null;
  let latestTime = -Infinity;

  for (const file of files) {
    let content;
    try {
      content = await readFile(file.path, "utf8");
    } catch {
      continue;
    }

    const lines = content.split(/\r?\n/);
    for (let index = lines.length - 1; index >= 0; index -= 1) {
      const status = tokenStatusFromLine(lines[index], file.path);
      if (!status) continue;
      const timestamp = Date.parse(status.timestamp || "");
      const score = Number.isFinite(timestamp) ? timestamp : file.mtimeMs;
      if (score > latestTime) {
        latest = status;
        latestTime = score;
      }
      break;
    }
  }

  return latest;
}

function formatPercent(value) {
  return Number.isFinite(value) ? `${Math.round(value)}%` : "알 수 없음";
}

export function renderStatusLines(status) {
  if (!status) {
    return [
      "토큰 상태를 찾지 못했습니다.",
      "아직 이 Codex Desktop 세션에 token_count 이벤트가 기록되지 않았을 수 있습니다.",
    ];
  }

  return [
    `5시간 한도: ${formatPercent(status.primary.usedPercent)}`,
    `주간 한도: ${formatPercent(status.secondary.usedPercent)}`,
    `5시간 리셋: ${status.primary.resetAtKst || "알 수 없음"}`,
    `주간 리셋: ${status.secondary.resetAtKst || "알 수 없음"}`,
    status.planType ? `플랜: ${status.planType}` : null,
  ].filter(Boolean);
}

export async function buildStatusAdditionalContext({ prompt, codexHome } = {}) {
  if (!isStatusPrompt(prompt)) return null;
  const status = await findLatestTokenStatus({ codexHome });
  const lines = renderStatusLines(status);
  return [
    "Codex Desktop local /상태 command was handled by a lightweight status hook.",
    "이 상태 정보만 간결하게 답변하고, 원인 설명이나 추가 계획은 붙이지 마세요.",
    ...lines,
  ].join("\n");
}
