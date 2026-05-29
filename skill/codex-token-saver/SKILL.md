---
name: codex-token-saver
description: Use when working in Codex on token-heavy coding tasks, noisy terminal output, broad repo exploration, context compaction, A/B token-saving checks, or when the user asks for maximum token savings without losing accuracy.
---

# Codex Token Saver

Use this skill to keep Codex context small while preserving exact raw evidence.

## Workflow

1. Prefer targeted context packs before broad reads:
   `cts pack --query "<task or symbol>" --root .`
2. For noisy shell output, capture raw text and show only compact facts:
   `some command | cts filter --capture --command "some command"`
3. Retrieve raw evidence only when needed:
   `cts get <id>` or `cts search "<term>"`
4. Find hidden token waste:
   `cts scan --root .`
5. Prove the setup:
   `cts ab-test --fixtures benchmarks/fixtures`
   `cts watchdog --run-tests --until-pass --max-runs 5`
6. For automatic Codex Desktop compaction, install the PostToolUse hook:
   `cts install-hook`

## Requirement Watchdog Subagent

For release checks or optimization loops, use `agents/requirement-watchdog.md`. It reruns `cts watchdog --run-tests --until-pass --max-runs 5`, enforces the 94% overall saving gate, the per-case floors, and anchor recall 100%.

## Codex Reply Rules

- Be concise by default, but do not drop paths, commands, error text, decisions, or verification evidence.
- Never pretend compact context is complete. If detail matters, retrieve the `ctx://capture/<id>` raw source.
- Use `AGENTS.md` as a short routing index. Move long procedures to docs and load them only when relevant.
- Keep raw outputs in SQLite, not in chat context.

## Install Shape

The Windows installer copies this skill to `%USERPROFILE%\.codex\skills\codex-token-saver` and creates the `cts` command shim in `%USERPROFILE%\.codex\bin`.
