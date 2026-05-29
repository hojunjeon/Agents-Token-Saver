from __future__ import annotations

from dataclasses import dataclass
import re


TOKEN_RE = re.compile(r"[A-Za-z0-9_]+|[^\sA-Za-z0-9_]", re.UNICODE)


@dataclass(frozen=True)
class CompactResult:
    text: str
    original_tokens: int
    optimized_tokens: int
    saving_ratio: float
    strategy: str


def estimate_tokens(text: str) -> int:
    """Stable local token estimate used for A/B comparisons.

    It is intentionally dependency-free. The absolute count will differ from a
    model tokenizer, but the same estimator is applied to baseline and
    optimized text so savings remain comparable.
    """

    if not text:
        return 0
    return max(1, len(TOKEN_RE.findall(text)))


def compact_output(text: str, command: str = "") -> CompactResult:
    command_l = command.lower()
    if "pytest" in command_l or "failures" in text.lower() or "passed in" in text.lower():
        compact = _compact_pytest(text)
        strategy = "pytest"
    elif command_l.strip().startswith("git status") or "changes not staged" in text.lower():
        compact = _compact_git_status(text)
        strategy = "git-status"
    else:
        compact = _compact_generic(text)
        strategy = "generic"

    original = estimate_tokens(text)
    optimized = estimate_tokens(compact)
    saving = 0.0 if original == 0 else max(0.0, 1.0 - optimized / original)
    return CompactResult(compact, original, optimized, saving, strategy)


def _strip_pytest_noise(line: str) -> str:
    line = re.sub(r"^E\s+", "", line.rstrip())
    return line


def _compact_pytest(text: str) -> str:
    lines = [_strip_pytest_noise(line) for line in text.splitlines()]
    kept: list[str] = []
    test_name = ""
    path_line = ""
    assert_line = ""
    summary = ""
    for line in lines:
        clean = line.strip()
        if not clean:
            continue
        if clean.startswith("___") and not test_name:
            test_name = clean.strip("_ ")
        elif not path_line and re.search(r"[\w./\\-]+\.py:\d+", clean):
            path_line = clean
        elif not assert_line and re.search(r"\bassert\s+.+", clean):
            assert_line = clean
        elif not summary and re.search(r"\d+\s+failed\b|\d+\s+error", clean, re.I):
            summary = _compact_pytest_summary(clean)
        elif clean.startswith("FAILED ") and not path_line:
            path_line = clean

    kept.append("pytest:" + (f" {test_name}" if test_name else " compacted"))
    kept.extend(line for line in [path_line, assert_line, summary] if line)
    return _dedupe_lines(kept)


def _compact_git_status(text: str) -> str:
    lines = text.splitlines()
    branch = ""
    relation = ""
    files: dict[str, list[str]] = {"M": [], "D": [], "A": [], "??": []}
    for line in lines:
        clean = line.strip()
        if not clean:
            continue
        if clean.startswith("On branch "):
            branch = clean.removeprefix("On branch ")
        elif "ahead of" in clean or "behind" in clean:
            relation = _compact_git_relation(clean)
        elif clean.startswith("modified:"):
            files["M"].append(clean.removeprefix("modified:").strip())
        elif clean.startswith("deleted:"):
            files["D"].append(clean.removeprefix("deleted:").strip())
        elif clean.startswith("new file:"):
            files["A"].append(clean.removeprefix("new file:").strip())
        elif re.match(r"^[\w./\\-]+\.[A-Za-z0-9]+$", clean):
            files["??"].append(clean)
    kept: list[str] = []
    if branch:
        kept.append(" ".join(part for part in ["branch", branch, relation] if part))
    for status in ["M", "D", "A", "??"]:
        if files[status]:
            kept.append(f"{status} {' '.join(_unique(files[status]))}")
    return _dedupe_lines(kept)


def _compact_pytest_summary(line: str) -> str:
    clean = line.strip("= ")
    match = re.search(r"(\d+\s+failed.*?in\s+[0-9.]+s)", clean, re.I)
    if match:
        return match.group(1)
    match = re.search(r"(\d+\s+errors?.*?in\s+[0-9.]+s)", clean, re.I)
    if match:
        return match.group(1)
    return clean


def _compact_git_relation(line: str) -> str:
    match = re.search(r"\bahead of\b.+?\bby\s+(\d+)\s+commit", line)
    if match:
        return f"ahead+{match.group(1)}"
    match = re.search(r"\bbehind\b.+?\bby\s+(\d+)\s+commit", line)
    if match:
        return f"behind+{match.group(1)}"
    return line


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            out.append(item)
            seen.add(item)
    return out


def _compact_generic(text: str) -> str:
    lines = text.splitlines()
    if len(lines) <= 24:
        return text.strip()
    interesting = [
        line.strip()
        for line in lines
        if re.search(r"error|failed|exception|traceback|warning|\.py:\d+|\.ts:\d+|\.rs:\d+", line, re.I)
    ]
    kept = ["[cts:generic] compacted output", *lines[:6], *interesting[:24], "...", *lines[-6:]]
    return _dedupe_with_omission([line.strip() for line in kept if line.strip()], len(lines))


def _dedupe_with_omission(lines: list[str], original_line_count: int) -> str:
    seen: set[str] = set()
    out: list[str] = []
    for line in lines:
        if line not in seen:
            out.append(line)
            seen.add(line)
    omitted = max(0, original_line_count - len(out))
    if omitted:
        out.append(f"[cts] omitted {omitted} low-signal lines.")
    return "\n".join(out).strip() + "\n"


def _dedupe_lines(lines: list[str]) -> str:
    seen: set[str] = set()
    out: list[str] = []
    for line in lines:
        if line not in seen:
            out.append(line)
            seen.add(line)
    return "\n".join(out).strip() + "\n"
