# Agents Token Saver

Token-saving adapters for agentic coding tools. The main implementation in this repository is a Windows/Codex Desktop Token Vault hook suite that keeps model performance intact by preserving exact tool output outside the model context while sending a compact, high-signal summary back to the agent. It also includes a `/상태` fallback hook, status CLI, and Codex skill so Desktop sessions can still surface 5-hour and weekly token quota data.

This repository also includes three imported reinstall packages for related hosts:

- `integrations/imported/openclaw-tokenjuice-vault-reinstall` - OpenClaw TokenJuice vault patch
- `integrations/imported/hermes-token-vault-reinstall` - Hermes `token-vault` plugin
- `integrations/imported/omx-token-vault-reinstall` - Original OMX/Codex token-vault hook package

The original `.tar.gz` bundles are preserved in `archives/`.

## Why This Exists

Most agent token waste comes from large tool results, not final prose. Logs, test output, repository-wide search, and generated JSON can flood the context window even when the agent only needs status, errors, head/tail lines, and a way to retrieve the exact original output.

Agents Token Saver uses a loss-aware pattern inspired by RTK-style output filtering, Context Mode-style external storage, and token optimizer MCP patterns:

1. Let tools run normally.
2. Detect large `PostToolUse` results.
3. Store the exact original payload locally.
4. Return a compact JSON summary with status, errors, head/tail lines, high-signal lines, byte counts, reduction percentage, and a retrieval path.
5. Bypass compaction when the agent intentionally reads vault artifacts.
6. Preserve Codex's native `/status` path and add `/상태` fallback surfaces without touching tool-output compaction.

Small outputs are left untouched.

## Main Feature: Windows Codex Desktop Token Vault

The Codex Desktop hook lives in:

- `src/token-vault-core.mjs`
- `src/codex-token-vault-hook.mjs`
- `src/codex-status-core.mjs`
- `src/codex-status-hook.mjs`
- `src/codex-status-cli.mjs`
- `skills/codex-token-status/SKILL.md`
- `scripts/install-token-vault.ps1`

It is designed for Windows Codex Desktop and keeps existing OMX hooks intact. Installation inserts the vault hook before the existing OMX `PostToolUse` hook, inserts the status hook before the existing OMX `UserPromptSubmit` hook, then records Codex hook trust hashes for all managed entries.

### Behavior

- Default threshold: `12,000` bytes
- Default summary budget: `4,000` chars
- Storage root: `%USERPROFILE%\.omx\token-vault-codex`
- Exact artifact storage: `%USERPROFILE%\.omx\token-vault-codex\artifacts\<id>.json`
- SQLite index when `node:sqlite` is available, JSONL fallback otherwise
- Redacts common secret-shaped fields in summaries: authorization, token, secret, password, API key, cookie, signature, private key
- Fail-open hook design: hook errors are logged and original tool behavior continues

### Desktop Status Command

Codex's own Desktop `/status` command is a built-in app slash command that shows thread ID, context usage, and rate limits. Built-in slash commands are handled by Codex before ordinary `UserPromptSubmit` hooks, so Token Vault does not intercept or replace the native `/status` command.

For Korean Desktop sessions, the installer adds two fallback surfaces for status prompts:

1. `codex-status-windows-shim.ps1` as the first `UserPromptSubmit` hook.
2. A user skill installed at `%USERPROFILE%\.codex\skills\codex-token-status\SKILL.md` with `name: "token-status"`.

The fallback hook reacts only if the prompt reaches `UserPromptSubmit` as:

```text
/상태
/status
```

Codex app built-in slash commands are handled before hooks, and custom skills are mentioned with `$`/`@` rather than `/`. If the Desktop slash parser does not pass `/상태` through, use `token-status`, `$token-status`, or a plain Korean prompt such as `상태` instead. Both fallback paths read the newest local `token_count` event from `%USERPROFILE%\.codex\sessions\**\*.jsonl`. Token Vault remains isolated on `PostToolUse`, so quota display and output compaction do not compete with each other.

Direct check:

```powershell
node "$HOME\.omx\token-vault-codex\bin\codex-status-cli.mjs"
```

### Install

From a PowerShell terminal:

```powershell
git clone https://github.com/hojunjeon/Agents-Token-Saver.git
cd Agents-Token-Saver
npm test
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\install-token-vault.ps1
```

Restart Codex Desktop or start a new Codex session after installing so the hook config is reloaded.

### Configure

Environment variables:

```powershell
$env:CODEX_TOKEN_VAULT = "1"                 # 0/false/no/off disables
$env:CODEX_TOKEN_VAULT_THRESHOLD = "12000"   # bytes before compaction
$env:CODEX_TOKEN_VAULT_MAX_CHARS = "4000"    # compact summary budget
$env:CODEX_TOKEN_VAULT_DIR = "$HOME\.omx\token-vault-codex"
```

### Uninstall

Remove the Token Vault `PostToolUse` entry and status `UserPromptSubmit` entry from `%USERPROFILE%\.codex\hooks.json`, then delete:

```powershell
Remove-Item -Recurse -Force "$HOME\.codex\hooks\codex-token-vault-windows-shim.ps1"
Remove-Item -Recurse -Force "$HOME\.codex\hooks\codex-status-windows-shim.ps1"
Remove-Item -Recurse -Force "$HOME\.omx\token-vault-codex"
```

The installer creates timestamped backups of `hooks.json` and `config.toml` before modifying them.

## Imported Integrations

### OpenClaw TokenJuice Vault

Path:

```text
integrations/imported/openclaw-tokenjuice-vault-reinstall
```

Install:

```bash
cd integrations/imported/openclaw-tokenjuice-vault-reinstall
./install.sh
```

Optional:

```bash
OPENCLAW_ROOT=/path/to/openclaw ./install.sh
```

Effect: large OpenClaw shell/tool results are stored under `~/.openclaw/token-vault/artifacts/` and compact summaries enter context.

### Hermes Token Vault

Path:

```text
integrations/imported/hermes-token-vault-reinstall
```

Install:

```bash
cd integrations/imported/hermes-token-vault-reinstall
./install.sh
```

Effect: large Hermes tool results are stored under `~/.hermes/token-vault/artifacts/` and compact summaries enter context.

### Original OMX Token Vault Package

Path:

```text
integrations/imported/omx-token-vault-reinstall
```

Install:

```bash
cd integrations/imported/omx-token-vault-reinstall
./install.sh
```

Effect: large Codex/OMX tool results are stored under `~/.omx/token-vault/artifacts/` and compact summaries enter context.

Note: this imported package was built around Unix-style paths such as `/usr/bin/node`. For Windows Codex Desktop, prefer the main implementation in this repository.

## Performance Evaluation

Measured locally on Windows Codex Desktop workspace with:

```powershell
npm run benchmark
```

| Scenario | Without Token Vault | With Token Vault | Reduction | Hook Time |
| --- | ---: | ---: | ---: | ---: |
| Large test log with failures | 241,022 bytes | 4,200 bytes | 98.3% | 20.63 ms |
| Repo-wide search output | 167,219 bytes | 5,942 bytes | 96.4% | 9.18 ms |
| Small command output | 17 bytes | 17 bytes | 0% | 0.04 ms |

The compactor leaves small outputs untouched and only rewrites results when the compact wrapper is meaningfully smaller than the original.

## Verification

```powershell
npm test
npm run benchmark
node --check .\src\codex-token-vault-hook.mjs
node --check .\src\token-vault-core.mjs
```

Current validation status:

- `npm test`: 11/11 passing
- `npm run benchmark`: 96.4-98.3% reduction on large synthetic outputs
- Installed Windows vault shim: emits compact Codex `PostToolUse` replacement output without warnings
- Installed Windows status shim: emits `UserPromptSubmit` status context for `/상태`, `/status`, and the Windows mojibake fallback `/??`
- Installed status CLI: prints current local 5-hour and weekly quota lines directly
- Installed status skill: exposes a `token-status` skill for Desktop skill routing

## Security Notes

The compact summary redacts common secret-shaped fields, but the exact original tool result is stored locally for retrieval. Avoid printing secrets in terminal commands. If sensitive output may have been captured, remove the relevant artifact from the vault directory.

## Repository Layout

```text
src/                         Windows/Codex Token Vault implementation
scripts/                     Installer for Codex Desktop on Windows
test/                        Node test runner coverage
tools/                       Benchmark script
integrations/imported/       Imported OpenClaw, Hermes, and OMX reinstall packages
archives/                    Original tar.gz bundles
```

## Related Projects And Ideas

- [Caveman](https://github.com/juliusbrussee/caveman) - output style compression
- [RTK](https://github.com/rtk-ai/rtk) - terminal output filtering
- [Context Mode](https://github.com/mksglu/context-mode) - out-of-context storage and session continuity
- [Token Optimizer MCP](https://github.com/ooples/token-optimizer-mcp) - MCP caching and compression patterns
