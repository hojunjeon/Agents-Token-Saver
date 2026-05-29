from __future__ import annotations

from pathlib import Path
import hashlib
import json
import re
import sys
import time

from .compactor import compact_output
from .store import ContextStore


DEFAULT_THRESHOLD_BYTES = 12_000
DEFAULT_HOOK_TIMEOUT_SECONDS = 30
SECRET_KEY_RE = re.compile(r"authorization|token|secret|password|api[_-]?key|cookie|signature|private[_-]?key", re.I)
SECRET_VALUE_RES = [
    re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]+"),
    re.compile(r"sk-[A-Za-z0-9_-]{12,}"),
    re.compile(r"(?i)\b(authorization|token|secret|password|api[_-]?key|cookie|signature|private[_-]?key)\s*[:=]\s*([^\s,;]+)"),
]


def compact_post_tool_use_payload(
    payload: dict,
    store: ContextStore,
    threshold_bytes: int = DEFAULT_THRESHOLD_BYTES,
) -> dict | None:
    event = payload.get("hook_event_name") or payload.get("hookEventName")
    if event != "PostToolUse":
        return None

    command = _command_from_payload(payload)
    raw = _raw_response_text(payload.get("tool_response"))
    original_bytes = len(raw.encode("utf-8", errors="replace"))
    if original_bytes < threshold_bytes or _is_capture_retrieval(command, payload):
        return None

    compact = compact_output(raw, command=command)
    capture = store.capture(str(payload.get("tool_name") or "PostToolUse"), raw, command=command)
    compact_text = _redact_context(compact.text)
    context = "\n".join(
        [
            "_codex_token_saver_hook",
            f"raw=ctx://capture/{capture.id} sha256={capture.sha256} bytes={capture.bytes} saving={compact.saving_ratio:.1%}",
            compact_text.strip(),
            "",
        ]
    )
    context_bytes = len(context.encode("utf-8", errors="replace"))
    if context_bytes >= original_bytes * 0.85:
        return None

    return {
        "continue": False,
        "stopReason": context,
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": context,
        },
    }


def install_post_tool_use_hook(
    codex_home: Path | str,
    db_path: Path | str,
    cts_command: str | None = None,
) -> Path:
    codex_home = Path(codex_home)
    hooks_dir = codex_home / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    shim = hooks_dir / "codex-token-saver-post-tool-use.ps1"
    hooks_json = codex_home / "hooks.json"
    db_path = Path(db_path)

    command = cts_command or f'"{sys.executable}" -m codex_token_saver'
    shim.write_text(_shim_script(command, db_path), encoding="utf-8")

    data = _read_hooks_json(hooks_json)
    hooks = data.setdefault("hooks", {})
    existing = hooks.setdefault("PostToolUse", [])
    existing = [entry for entry in existing if "codex-token-saver-post-tool-use.ps1" not in json.dumps(entry)]
    hook_command = f'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "{shim}"'
    new_entry = {
        "hooks": [
            {
                "type": "command",
                "command": hook_command,
                "timeout": DEFAULT_HOOK_TIMEOUT_SECONDS,
                "statusMessage": "Compacting large tool output",
            }
        ]
    }
    hooks["PostToolUse"] = [new_entry, *existing]
    trust_rows = _trust_post_tool_use_hooks(data, hooks_json)

    stamp = int(time.time())
    if hooks_json.exists():
        backup = hooks_json.with_name(hooks_json.name + f".bak-codex-token-saver-{stamp}")
        backup.write_text(hooks_json.read_text(encoding="utf-8"), encoding="utf-8")
    hooks_json.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    _write_config_trust_state(codex_home / "config.toml", trust_rows, stamp)
    return shim


def _raw_response_text(value: object) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, indent=2)


def _command_from_payload(payload: dict) -> str:
    tool_input = payload.get("tool_input")
    if isinstance(tool_input, dict):
        return str(tool_input.get("command") or "")
    return ""


def _is_capture_retrieval(command: str, payload: dict) -> bool:
    haystack = " ".join([command, json.dumps(payload.get("tool_input", ""), ensure_ascii=False)]).lower()
    return "ctx://capture/" in haystack or " cts get " in f" {haystack} " or "codex_token_saver get" in haystack


def _redact_context(text: str) -> str:
    redacted = text
    for pattern in SECRET_VALUE_RES:
        if pattern.pattern.startswith("(?i)\\b("):
            redacted = pattern.sub(lambda match: f"{match.group(1)}: [REDACTED]", redacted)
        else:
            redacted = pattern.sub("[REDACTED]", redacted)
    lines: list[str] = []
    for line in redacted.splitlines():
        if SECRET_KEY_RE.search(line) and "[REDACTED]" not in line:
            key = line.split(":", 1)[0] if ":" in line else line.split("=", 1)[0]
            lines.append(f"{key}: [REDACTED]")
        else:
            lines.append(line)
    return "\n".join(lines) + ("\n" if text.endswith("\n") else "")


def _read_hooks_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return {}


def _trust_post_tool_use_hooks(data: dict, hooks_json: Path) -> list[dict[str, str]]:
    state = data.setdefault("state", {})
    rows: list[dict[str, str]] = []
    post_tool_use_entries = data.get("hooks", {}).get("PostToolUse", [])
    for group_index, entry in enumerate(post_tool_use_entries):
        for handler_index, hook in enumerate(entry.get("hooks", [])):
            if hook.get("type") != "command":
                continue
            identity = {
                "event_name": "post_tool_use",
                **({"matcher": entry["matcher"]} if "matcher" in entry else {}),
                "hooks": [
                    {
                        "type": "command",
                        "command": hook.get("command", ""),
                        "timeout": max(1, int(hook.get("timeout", 600))),
                        "async": False,
                        **({"statusMessage": hook["statusMessage"]} if hook.get("statusMessage") else {}),
                    }
                ],
            }
            trusted_hash = "sha256:" + hashlib.sha256(
                json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest()
            key = f"{hooks_json}:post_tool_use:{group_index}:{handler_index}"
            state[key] = {"trusted_hash": trusted_hash}
            rows.append({"key": key, "trusted_hash": trusted_hash})
    return rows


def _write_config_trust_state(config_toml: Path, rows: list[dict[str, str]], stamp: int) -> None:
    if not rows:
        return
    config_toml.parent.mkdir(parents=True, exist_ok=True)
    if config_toml.exists():
        backup = config_toml.with_name(config_toml.name + f".bak-codex-token-saver-trust-{stamp}")
        backup.write_text(config_toml.read_text(encoding="utf-8"), encoding="utf-8")
        text = config_toml.read_text(encoding="utf-8-sig")
    else:
        text = ""

    for row in rows:
        section = f'[hooks.state."{_toml_escape_key(row["key"])}"]'
        block = f'{section}\ntrusted_hash = "{row["trusted_hash"]}"'
        pattern = re.escape(section) + r'\s*\r?\ntrusted_hash = "[^"]+"'
        if re.search(pattern, text):
            text = re.sub(pattern, block, text, count=1)
        else:
            if text and not text.endswith(("\n", "\r")):
                text += "\n"
            text += f"\n{block}\n"
    config_toml.write_text(text, encoding="utf-8")


def _toml_escape_key(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _shim_script(cts_command: str, db_path: Path) -> str:
    quoted_db = str(db_path).replace("'", "''")
    return f"""$ErrorActionPreference = 'Stop'
$stdinPayload = [Console]::In.ReadToEnd()
$startInfo = [System.Diagnostics.ProcessStartInfo]::new()
$startInfo.FileName = 'cmd.exe'
$startInfo.UseShellExecute = $false
$startInfo.RedirectStandardInput = $true
$startInfo.RedirectStandardOutput = $true
$startInfo.RedirectStandardError = $true
$startInfo.Arguments = '/c {cts_command} hook post-tool-use --db "{quoted_db}"'
$process = [System.Diagnostics.Process]::new()
$process.StartInfo = $startInfo
$null = $process.Start()
$stdoutTask = $process.StandardOutput.ReadToEndAsync()
$stderrTask = $process.StandardError.ReadToEndAsync()
$process.StandardInput.Write($stdinPayload)
$process.StandardInput.Close()
$process.WaitForExit()
[Console]::Out.Write($stdoutTask.Result)
[Console]::Error.Write($stderrTask.Result)
exit $process.ExitCode
"""
