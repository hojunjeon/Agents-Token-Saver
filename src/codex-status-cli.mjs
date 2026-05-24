#!/usr/bin/env node
import { stdout } from "node:process";

import {
  findLatestTokenStatus,
  getDefaultCodexHome,
  renderStatusLines,
} from "./codex-status-core.mjs";

async function main() {
  const status = await findLatestTokenStatus({ codexHome: getDefaultCodexHome() });
  stdout.write(`${renderStatusLines(status).join("\n")}\n`);
}

main().catch((error) => {
  stdout.write(`토큰 상태 확인 실패: ${String(error?.message || error)}\n`);
});
