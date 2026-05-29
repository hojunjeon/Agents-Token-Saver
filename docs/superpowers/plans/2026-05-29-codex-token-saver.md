# Codex Token Saver Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Codex-native token-saving toolkit with tests, Windows install, docs, and A/B proof.

**Architecture:** Pure Python stdlib CLI plus Codex skill assets. SQLite stores raw context, compactors and symbol packs reduce active Codex tokens, and the watchdog verifies release gates.

**Tech Stack:** Python 3.11 stdlib, unittest, SQLite, PowerShell, Codex skills.

---

### Task 1: Compactor

**Files:**
- Create: `codex_token_saver/compactor.py`
- Test: `tests/test_compactor.py`

- [x] Write failing tests for pytest and git status compaction.
- [x] Implement deterministic compactors.
- [ ] Run tests and verify pass.

### Task 2: Store And Pack

**Files:**
- Create: `codex_token_saver/store.py`
- Create: `codex_token_saver/symbols.py`
- Create: `codex_token_saver/packer.py`
- Test: `tests/test_store_and_pack.py`

- [x] Write failing tests for SQLite capture and symbol pack.
- [x] Implement store, symbol extraction, and packer.
- [ ] Run tests and verify pass.

### Task 3: Codex Assets And Watchdog

**Files:**
- Create: `codex_token_saver/ab_test.py`
- Create: `codex_token_saver/watchdog.py`
- Create: `skill/codex-token-saver/SKILL.md`
- Create: `install.bat`
- Create: `install.ps1`
- Test: `tests/test_codex_assets_and_watchdog.py`

- [x] Write failing tests for assets, A/B CLI, and watchdog.
- [x] Implement CLI, installer, docs, fixtures, and watchdog.
- [ ] Run tests, generate A/B report, then rerun watchdog.
