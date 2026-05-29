# Codex Token Saver A/B Test Results

Baseline sends raw terminal/file context. Optimized sends compact facts plus SQLite `ctx://` references.

- Overall baseline tokens: 2008
- Overall optimized tokens: 111
- Overall saving: 94.5%
- Anchor recall: 100%
- Runtime: 7.308 ms

| Case | Type | Baseline | Optimized | Saving | Recall |
|---|---:|---:|---:|---:|---:|
| git_status_verbose | terminal-output | 99 | 48 | 51.5% | 100% |
| pytest_failure | terminal-output | 642 | 26 | 96.0% | 100% |
| symbol-pack | codex-context-pack | 1267 | 37 | 97.1% | 100% |
