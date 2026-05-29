---
title: Codex Hook Installers Must Write Trust State
date: 2026-05-29
category: integration-issues
module: Codex Token Saver
problem_type: integration_issue
component: tooling
symptoms:
  - "Installer writes hooks.json and reports success, but Codex Desktop can still skip the hook until trust state exists"
  - "A pre-push review can pass functional hook tests while missing the actual Desktop execution precondition"
  - "Old installer behavior is accidentally lost when porting hooks between runtimes"
root_cause: missing_workflow_step
resolution_type: code_fix
severity: high
related_components:
  - development_workflow
  - testing_framework
tags:
  - codex-token-saver
  - post-tool-use-hook
  - trust-state
  - windows-installer
  - fail-open
---

# Codex Hook Installers Must Write Trust State

## Problem

The Python `cts install-hook` port initially wrote a Windows shim and prepended a `PostToolUse` entry to `hooks.json`, but it did not recreate the trusted hook state that the old Node installer generated. That meant installation could look successful while Codex Desktop still had a reason to avoid executing the hook automatically.

## Symptoms

- The installer printed success and created the shim.
- Tests proved `cts hook post-tool-use` worked, but not that Codex would trust the installed command.
- The old repo's most valuable automatic-hook behavior was only partially preserved.

## What Didn't Work

- Treating `hooks.json` registration as sufficient missed Codex Desktop's trust layer.
- Porting only the hook runtime ignored installer behavior that was not in the hook itself.
- Relying on manual approval instructions would make the "one-click" Windows installer weaker than the old package.

## Solution

Generate trust state from the canonical command-hook identity whenever installing the hook:

```python
identity = {
    "event_name": "post_tool_use",
    "hooks": [{
        "type": "command",
        "command": hook.get("command", ""),
        "timeout": max(1, int(hook.get("timeout", 600))),
        "async": False,
        "statusMessage": hook["statusMessage"],
    }],
}
trusted_hash = "sha256:" + hashlib.sha256(
    json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
).hexdigest()
```

Write the resulting hash to both `hooks.json` state and `config.toml`:

```toml
[hooks.state."C:\\Users\\...\\.codex\\hooks.json:post_tool_use:0:0"]
trusted_hash = "sha256:..."
```

Add installer tests that assert the exact hash exists, plus a fail-open test proving hook error logging cannot turn a hook failure into a nonzero CLI exit.

## Why This Works

The hook command, timeout, status message, event name, and matcher form the trust identity Codex evaluates. Writing the matching hash during install preserves the old automatic vault behavior while keeping the Python implementation self-contained.

## Prevention

- When porting a hook, compare installer side effects, not only runtime behavior.
- Test the integration preconditions Codex needs to execute a hook: shim, hook entry, trusted hash, and config persistence.
- Keep hook CLIs fail-open even if the error log path itself is broken.

## Related Issues

- `codex_token_saver/hook.py`
- `codex_token_saver/__main__.py`
- `tests/test_hook_and_install.py`
- `install.ps1`
