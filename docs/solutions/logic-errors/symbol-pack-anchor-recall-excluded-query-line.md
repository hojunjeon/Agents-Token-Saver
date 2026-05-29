---
title: Symbol Pack Recall Must Exclude Echoed Query Lines
date: 2026-05-29
category: logic-errors
module: Codex Token Saver
problem_type: logic_error
component: tooling
symptoms:
  - "Symbol-pack anchor recall was tautological because the query line was echoed into the packed output"
  - "Recall was measured over the full pack instead of evidence chunks only"
  - "Quality gates could pass without proving that unrelated evidence was excluded"
root_cause: logic_error
resolution_type: code_fix
severity: high
related_components:
  - testing_framework
tags:
  - codex-token-saver
  - symbol-pack
  - recall-metric
  - packer
  - evidence-chunks
  - watchdog
---

# Symbol Pack Recall Must Exclude Echoed Query Lines

## Problem

`ContextPacker.build_pack()` echoed the query into the compact pack and then measured `_anchor_recall()` over the entire pack. That let the `symbol-pack` benchmark report `100%` recall from the query header alone, even when the selected source evidence did not contain the anchors.

## Symptoms

- Reviewers could reproduce `recall=1.0` with unrelated fallback evidence.
- The watchdog's "without anchor loss" gate trusted that inflated recall value.
- A/B savings could improve while silently weakening source-evidence quality.

## What Didn't Work

- Positive recall tests were not enough because the fixture query and selected symbol happened to match.
- Keeping `q reject expired token` in the measured text made the metric tautological.
- Checking only overall savings missed whether recall came from evidence or scaffolding.

## Solution

Measure recall against evidence chunks only, excluding the echoed query line:

```python
pack_text = "\n".join(chunks).strip() + "\n"
optimized_tokens = estimate_tokens(pack_text)
saving = 0.0 if baseline_tokens == 0 else max(0.0, 1.0 - optimized_tokens / baseline_tokens)
recall = _anchor_recall(query, "\n".join(chunks[1:]))
return ContextPack(pack_text, baseline_tokens, optimized_tokens, saving, recall, raw_refs)
```

Add a negative test where the pack contains the query header but the selected evidence is unrelated:

```python
pack = ContextPacker(root, store).build_pack("reject expired token", token_budget=120)

self.assertIn("q reject expired token", pack.text)
self.assertIn("compute_total", pack.text)
self.assertLess(pack.anchor_recall, 1.0)
```

Then keep the compact symbol output minimal while preserving anchors:

```text
q reject expired token
fn reject_expired_token src\auth.py:6 ctx://capture/1
      if response.status_code != 401:
          raise AssertionError("expired token accepted")
```

## Why This Works

The query line still preserves user intent, but it no longer proves retrieval quality. Recall must now come from selected symbol metadata, path/line evidence, source behavior, or the raw `ctx://capture/<id>` recovery path.

## Prevention

- Add negative metric tests whenever a quality gate can be satisfied by scaffolding text.
- Keep savings, recall, runtime, per-case floors, raw retrieval, and ZIP hygiene under watchdog tests.
- When optimizing prompts or packs, identify which tokens are evidence and which are protocol before measuring quality.

## Related Issues

- `codex_token_saver/packer.py`
- `tests/test_extreme_efficiency.py`
- `codex_token_saver/watchdog.py`
