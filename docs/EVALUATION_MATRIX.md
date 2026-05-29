# Codex Token Saver Extreme Evaluation Matrix

Date: 2026-05-29

## Requirement Watcher

`codex_token_saver.watchdog.RequirementWatchdog` is the headless requirement watcher for this package. It now fails the release if any of these gates regress:

| Gate | Required |
|---|---:|
| Overall A/B saving | >= 94% |
| Anchor recall | 100% |
| A/B runtime | <= 1000 ms |
| Codex PostToolUse hook | tested and present |
| `git_status_verbose` saving | >= 50% |
| `pytest_failure` saving | >= 85% |
| `symbol-pack` saving | >= 95% |
| Requirement watchdog subagent asset | present in `skill/codex-token-saver/agents/requirement-watchdog.md` |
| Automated tests | `unittest discover` returns 0 |

## Optimization Attempts

| Attempt | Change | Baseline Tokens | Optimized Tokens | Overall Saving | Anchor Recall | Result |
|---|---|---:|---:|---:|---:|---|
| 0 | Original implementation | 2008 | 398 | 80.2% | 100% | Passed old 75% gate, not extreme enough |
| 1 | Terse pytest/git compaction, compact pack layout, SQLite capture dedupe | 2008 | 199 | 90.1% | 100% | Better, but symbol pack still carried weak one-term matches |
| 2 | Multi-term symbol coverage filter | 2008 | 142 | 92.9% | 100% | Near target; only header/protocol overhead remained |
| 3 | Shortest safe pack header while keeping `ctx://` exact-source rule | 2008 | 133 | 93.4% | 100% | Passed the previous gate, but still carried dead section labels |
| 4 | Remove dead symbol-pack labels while preserving query, path/line, source, and `ctx://capture` | 2008 | 117 | 94.2% | 100% | Passed new 94% gate |
| 5 | Measure recall against evidence only and drop duplicated source signature line | 2008 | 111 | 94.5% | 100% | Final accepted gate |
| 6 | Port existing repo's Windows PostToolUse token-vault hook into `cts hook post-tool-use` and `cts install-hook` | 2008 | 111 | 94.5% | 100% | Preserves remote automatic-hook advantage without Node runtime package |
| 7 | Restore trusted hook state generation from the old Windows installer and harden hook fail-open logging | 2008 | 111 | 94.5% | 100% | Keeps automatic hook execution reliable while preserving savings |

## Final Case Scores

| Case | Type | Baseline | Optimized | Saving | Recall | Floor |
|---|---|---:|---:|---:|---:|---:|
| `git_status_verbose` | terminal output | 99 | 48 | 51.5% | 100% | 50% |
| `pytest_failure` | terminal output | 642 | 26 | 96.0% | 100% | 85% |
| `symbol-pack` | Codex context pack | 1267 | 37 | 97.1% | 100% | 95% |

## Stop Rule

Further savings are bounded by irreducible anchors:

- `git_status_verbose` must still carry branch/relation plus every changed path.
- `pytest_failure` must still carry failing test name, file/line, assertion, and summary.
- `symbol-pack` must still carry the query, raw `ctx://` restore pointer, selected symbol path/line, and minimum source needed to answer.

Past attempt 5, additional reductions would remove either exact path evidence, failure diagnosis evidence, behavior evidence, the query anchor, or the raw-source recovery instruction. That would improve the token number while weakening Codex correctness, so the optimization loop stops here.

## Reproduction

```powershell
python -m codex_token_saver ab-test --fixtures benchmarks/fixtures --json docs/ab-test-results.json --markdown docs/AB_TEST_RESULTS.md
python -m codex_token_saver watchdog --run-tests --until-pass --max-runs 5 --output docs/WATCHDOG_REPORT.md
python -m unittest discover -s tests -v
```
