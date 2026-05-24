---
name: "상태"
description: "Show the current Codex token status from local session telemetry, including 5-hour and weekly limits. Use when the user types /상태 or asks for Codex token quota status in Korean."
---

# Codex Token Status

When this skill is invoked, report only the current token status.

Run:

```powershell
node "$env:USERPROFILE\.omx\token-vault-codex\bin\codex-status-cli.mjs"
```

Then answer with the command output only. Do not add a plan, explanation, or extra commentary.
