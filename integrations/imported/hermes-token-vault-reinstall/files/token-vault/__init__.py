"""Hermes Token Vault: compact large tool results without losing data.

The plugin intercepts tool results before they are appended to LLM context.
Large outputs are written to ~/.hermes/token-vault/artifacts/<id>.json and a
SQLite index, then replaced with a compact JSON object that preserves status,
errors, head/tail context, high-signal lines, and the artifact path for exact
retrieval.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import time
from pathlib import Path
from typing import Any

from hermes_constants import get_hermes_home

DEFAULT_THRESHOLD = 12_000
DEFAULT_MAX_CHARS = 4_000
MAX_SIGNAL_LINES = 80
LINE_RE = re.compile(r"(error|exception|traceback|failed|failure|warning|warn|critical|fatal|denied|timeout|not found|no such file|assert)", re.I)


def register(ctx):
    ctx.register_hook("transform_tool_result", transform_tool_result)


def _enabled() -> bool:
    return os.getenv("HERMES_TOKEN_VAULT", "1").strip().lower() not in {"0", "false", "no", "off"}


def _threshold() -> int:
    try:
        return int(os.getenv("HERMES_TOKEN_VAULT_THRESHOLD", str(DEFAULT_THRESHOLD)))
    except Exception:
        return DEFAULT_THRESHOLD


def _max_chars() -> int:
    try:
        return int(os.getenv("HERMES_TOKEN_VAULT_MAX_CHARS", str(DEFAULT_MAX_CHARS)))
    except Exception:
        return DEFAULT_MAX_CHARS


def _paths(vault_id: str) -> tuple[Path, Path, Path]:
    root = get_hermes_home() / "token-vault"
    artifacts = root / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    return root, root / "results.db", artifacts / f"{vault_id}.json"


def _stable_id(tool_name: str, result: str) -> str:
    h = hashlib.sha256()
    h.update(tool_name.encode("utf-8", "ignore"))
    h.update(b"\0")
    h.update(result.encode("utf-8", "ignore"))
    return h.hexdigest()[:16]


def _store(vault_id: str, tool_name: str, args: Any, result: str, duration_ms: int | None) -> Path:
    root, db_path, artifact_path = _paths(vault_id)
    artifact = {
        "id": vault_id,
        "tool_name": tool_name,
        "args": args,
        "duration_ms": duration_ms,
        "stored_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "result": result,
    }
    artifact_path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")
    con = sqlite3.connect(db_path)
    try:
        con.execute(
            "CREATE TABLE IF NOT EXISTS results (id TEXT PRIMARY KEY, tool_name TEXT, artifact_path TEXT, original_bytes INTEGER, stored_at REAL, duration_ms INTEGER)"
        )
        con.execute(
            "INSERT OR REPLACE INTO results VALUES (?, ?, ?, ?, ?, ?)",
            (vault_id, tool_name, str(artifact_path), len(result.encode("utf-8", "ignore")), time.time(), duration_ms),
        )
        con.commit()
    finally:
        con.close()
    return artifact_path


def _line_sample(text: str, budget: int) -> dict[str, Any]:
    lines = text.splitlines()
    if not lines:
        return {"line_count": 0, "excerpt": text[:budget]}
    head_n = min(40, max(10, budget // 140))
    tail_n = min(40, max(10, budget // 160))
    signal = []
    for i, line in enumerate(lines, 1):
        if LINE_RE.search(line):
            signal.append(f"{i}: {line[:240]}")
            if len(signal) >= MAX_SIGNAL_LINES:
                break
    head = [f"{i}: {line[:240]}" for i, line in enumerate(lines[:head_n], 1)]
    start_tail = max(len(lines) - tail_n, head_n)
    tail = [f"{i}: {line[:240]}" for i, line in enumerate(lines[start_tail:], start_tail + 1)]
    return {
        "line_count": len(lines),
        "head": head,
        "signal_lines": signal,
        "tail": tail,
        "omitted_lines": max(0, len(lines) - len(head) - len(tail)),
    }


def _truncate_str(value: str, budget: int) -> Any:
    if len(value) <= budget:
        return value
    sample = _line_sample(value, budget)
    sample["original_chars"] = len(value)
    sample["truncated"] = True
    return sample


def _compact_json(obj: Any, budget: int, depth: int = 0) -> Any:
    if depth > 5:
        return "<max-depth elided>"
    if isinstance(obj, str):
        return _truncate_str(obj, max(600, budget // (depth + 1)))
    if isinstance(obj, list):
        if len(obj) <= 40:
            return [_compact_json(x, max(500, budget // max(1, len(obj))), depth + 1) for x in obj]
        head = [_compact_json(x, 700, depth + 1) for x in obj[:25]]
        tail = [_compact_json(x, 700, depth + 1) for x in obj[-10:]]
        return {"items_head": head, "items_tail": tail, "omitted_items": len(obj) - 35, "total_items": len(obj)}
    if isinstance(obj, dict):
        keep = {}
        # status/error metadata first
        priority = ["success", "status", "exit_code", "error", "stderr", "duration", "duration_ms", "total_lines", "total_count", "file_size", "truncated", "hint"]
        for key in priority:
            if key in obj:
                keep[key] = _compact_json(obj[key], 1800, depth + 1)
        for key, val in obj.items():
            if key in keep:
                continue
            if len(keep) >= 28:
                keep.setdefault("_omitted_keys", 0)
                keep["_omitted_keys"] += 1
                continue
            # Generous handling for main payload fields, smaller for metadata.
            child_budget = 2600 if key in {"output", "content", "matches", "files", "messages"} else 900
            keep[key] = _compact_json(val, child_budget, depth + 1)
        return keep
    return obj


def _semantic_compact(tool_name: str, parsed: Any, raw: str, max_chars: int) -> Any:
    if isinstance(parsed, dict):
        compact = _compact_json(parsed, max_chars)
        # Terminal/execute_code outputs benefit from explicit signal extraction.
        output = parsed.get("output") or parsed.get("content") or ""
        if isinstance(output, str) and len(output) > 1000:
            compact["_signal_excerpt"] = _line_sample(output, max_chars)
        return compact
    return _truncate_str(raw, max_chars)


def transform_tool_result(tool_name=None, args=None, result=None, duration_ms=None, **_kwargs):
    if not _enabled() or not isinstance(result, str):
        return None
    # Exact retrieval escape hatch: when the agent intentionally opens a vault
    # artifact, do not compact it again. The caller can use read_file offset/limit
    # to inspect precise slices of the stored original result.
    if str(tool_name or "") == "read_file" and isinstance(args, dict):
        path = str(args.get("path") or "")
        if "/token-vault/artifacts/" in path:
            return None
    original_bytes = len(result.encode("utf-8", "ignore"))
    if original_bytes < _threshold():
        return None

    # Do not compact approval/errors that are already small enough to be actionable.
    try:
        parsed = json.loads(result)
    except Exception:
        parsed = None

    vault_id = _stable_id(str(tool_name or "tool"), result)
    artifact_path = _store(vault_id, str(tool_name or "tool"), args or {}, result, duration_ms)
    compact_payload = _semantic_compact(str(tool_name or "tool"), parsed if parsed is not None else result, result, _max_chars())
    wrapper = {
        "_token_vault": {
            "id": vault_id,
            "full_result_path": str(artifact_path),
            "original_bytes": original_bytes,
            "policy": "loss-aware semantic head/tail + error/signal preservation",
            "retrieve": "Use read_file on full_result_path for exact original tool result if needed.",
        },
        "tool_name": tool_name,
        "compact_result": compact_payload,
    }
    text = json.dumps(wrapper, ensure_ascii=False, separators=(",", ":"))
    # If the wrapper failed to save meaningful space, leave original untouched.
    if len(text.encode("utf-8", "ignore")) >= original_bytes * 0.85:
        return None
    wrapper["_token_vault"]["compact_bytes"] = len(text.encode("utf-8", "ignore"))
    wrapper["_token_vault"]["reduction_pct"] = round(100 * (1 - wrapper["_token_vault"]["compact_bytes"] / original_bytes), 1)
    return json.dumps(wrapper, ensure_ascii=False, separators=(",", ":"))
