# Repository Analysis for Codex Token Saver

Snapshot date: 2026-05-29. Shallow clones were inspected under `research/repos`.

| Repo | Inspected ref | Pattern reused for Codex |
|---|---:|---|
| `juliusbrussee/caveman` | `655b7d9` | Concise reply rules work when phrased as a small skill and reinforced by agent instructions. This project also ships `AGENTS.md`, so Codex should get native instructions, not only Claude files. |
| `rtk-ai/rtk` | `878af7d` | Command-specific compactors save most terminal-output tokens. We used a deterministic stdlib compactor for pytest and git status first, with a generic fallback. |
| `tirth8205/code-review-graph` | `0c9a5ff` | Structural context beats broad file reads. The Codex adaptation is a symbol pack with raw refs rather than a full Tree-sitter graph, keeping install friction low on Windows. |
| `mksglu/context-mode` | `a5f1fb7` | Sandbox raw outputs in SQLite and retrieve by search or id. Codex Token Saver stores raw captures in SQLite and emits `ctx://capture/<id>`. |
| `nadimtuhin/claude-token-optimizer` | `869df93` | Keep startup files short and route old docs through indexes. `cts init` writes a small `AGENTS.md` and leaves long procedures in docs. |
| `alexgreensh/token-optimizer` | `2ed938c` | Codex differs from Claude Code: `AGENTS.md`, `%USERPROFILE%\.codex`, hook trust state, and quality gates matter. This build installs a Codex skill, watchdog, and tested PostToolUse hook instead of assuming Claude hooks. |
| `ooples/token-optimizer-mcp` | `45a76c3` | Cache/compress large tool results externally. This build implements the core idea with local SQLite and no MCP dependency. |
| `zilliztech/claude-context` | `56b3751` | Retrieval should bring only relevant code into context. We use local lexical symbol scoring so Windows install stays one-click and offline. |
| `drona23/claude-token-efficient` | `b32fa8b` | Terse instruction files help only if they remain short. The Codex skill warns not to spend more input tokens than it saves. |
| `mibayy/token-savior` | `ff42ef1` | Symbol navigation, Bash compactors, and capture retrieval preserve performance while reducing active tokens. We implemented those three as the minimum useful Codex subset. |

## Codex-specific synthesis

Codex should not receive Claude-only files as the main interface. The deliverable therefore uses:

- `skill/codex-token-saver/SKILL.md` for Codex skill discovery.
- `install.bat` and `install.ps1` for Windows one-click installation.
- `cts init` to create a compact `AGENTS.md` routing file.
- A headless requirement watchdog that can be run from Codex until all gates pass.

The design keeps explicit shell pipelines and context packs as the stable default. Users can also opt into the tested Windows Codex `PostToolUse` hook via `cts install-hook`; the installer writes Codex trust state for automatic execution, and compact hook context redacts common secret-shaped values while SQLite retains exact raw output for local retrieval.
