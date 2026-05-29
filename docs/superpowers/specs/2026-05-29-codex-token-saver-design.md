# Codex Token Saver Design

## Goal

Build a Codex-native token-saving toolkit that reduces active context while preserving raw evidence and verification quality.

## Architecture

The tool has four layers: terminal output compactors, SQLite raw capture storage, symbol-focused context packing, and a requirement watchdog. Codex integration is a skill plus a Windows installer, with optional `AGENTS.md` generation per repo.

## Data flow

Noisy output enters `cts filter --capture`, is compacted for Codex, and is stored in SQLite for exact retrieval. Code context enters `cts pack`, is scored by query terms and symbols, and returns snippets plus `ctx://capture/<id>` refs.

## Testing

The test suite verifies token savings, raw round trip, symbol pack recall, install assets, CLI A/B metrics, and watchdog release gates.
