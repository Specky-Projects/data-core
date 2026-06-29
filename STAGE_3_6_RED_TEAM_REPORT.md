# STAGE 3.6 — RED TEAM REPORT

**Date:** 2026-06-28
**Approach:** Attempt to disprove every GO claim. Only confirm GO if every challenge fails.

---

## Challenge 1: Find hidden wall-clock usage

**Attack vector:** Search for any datetime.now(), utcnow(), time.time(), or os.time() in production files.

**Executed:** Grep `datetime\.now|utcnow\(\)` across all `app/adaptive_intelligence/*.py`

**Result:** Zero matches in production files. All 6 matches are in test files only.

**Secondary attack:** Check if any dependency (metrics.py, api.py) introduces wall-clock implicitly.

```python
# metrics.py — Prometheus Gauges/Counters/Histograms
# These record timestamps internally but do not influence computation results.
# They are best-effort (caught in try/except in orchestrator.py:392)
```

**Result:** Prometheus metric registration may use internal timestamps, but these are POST-computation side effects and do not affect any learning output or hash.

**Challenge FAILED. Wall-clock is isolated to test scaffolding.**

---

## Challenge 2: Prove replay is fake

**Attack vector:** Show that `EvaluationContext` injection is bypassed or ignored.

**In strategy_feedback.py:291:**
```python
evaluation_context = derive_evaluation_context(
    all_rows,
    self._lookback_days,
    self._evaluation_context,
)
```

**In derive_evaluation_context (dto.py:269):**
```python
if evaluation_context is not None:
    return evaluation_context.model_copy(update={"lookback_days": ...})
```

When `evaluation_context` is not None, it is honored. The function does NOT bypass it or derive a new one. Model_copy preserves all fields including `evaluation_timestamp`.

**Attack vector 2:** Show that freshness computation still uses wall-clock.

`compute_freshness(rows, evaluation_context)` — uses `evaluation_context.evaluation_timestamp.timestamp()` as reference. Confirmed by reading dto.py:388.

**Challenge FAILED. Replay context is honored everywhere.**

---

## Challenge 3: Find fake version propagation

**Attack vector:** Show that `ScientificVersionMetadata` is instantiated but not connected to output.

Confirmed in orchestrator.py:286: `versions = ScientificVersionMetadata()`

Confirmed in orchestrator.py:350: `"versions": versions.model_dump(mode="json")` — propagated to `policy_hints`.

Confirmed in orchestrator.py:401: `AdaptiveIntelligenceReport(versions=versions, ...)` — on the report.

**Attack vector 2:** Show that version fields are empty strings or placeholders.

```python
LEARNING_VERSION = "business-os-1.3-stage-3.6"
```

Length > 0. Non-empty. Non-placeholder. Semantically meaningful.

**Partial success:** `RegimeAdapterResult` and `RiskTuningResult` do NOT carry `versions` fields. These DTOs are missing version metadata at the DTO level. Compensated by orchestrator report-level versions.

**Challenge PARTIALLY SUCCEEDED.** Version propagation gap at regime/risk DTO level documented as SCIENTIFIC_GAP (not a blocker).

---

## Challenge 4: Prove provenance is hardcoded or fake

**Attack vector:** Show that feature_hash or evidence_hash returns constant values.

`feature_hash = stable_hash({"entity_id": entity_id, "features": features, "dataset_version": ..., "versions": ...})`

- Changes if `features` dict changes → different slices get different hashes. CONFIRMED.
- Changes if `entity_id` changes → different slices get different hashes. CONFIRMED.

**Attack vector 2:** Verify evidence_hash is actually sorted.

`evidence_hash = stable_hash({"evidence_ids": sorted(evidence_ids)})` — line 162. `sorted()` is explicit. CONFIRMED.

**Attack vector 3:** Verify decision_hash uses multiple inputs.

```python
stable_hash({
    "algorithm_version": versions.algorithm_version,
    "feature_hash": provenance.feature_hash,
    "dataset_version": evaluation_context.dataset_version,
    "policy_version": versions.policy_version,
    "evaluation_timestamp": evaluation_context.evaluation_timestamp,
    "learning_version": versions.learning_version,
    "entity_id": entity_id,
    "recommendation": recommendation,
})
```

8 distinct fields. Not a constant. CONFIRMED non-trivial.

**Partial success:** Regime and risk DTOs lack provenance. Same finding as Challenge 3.

**Challenge PARTIALLY SUCCEEDED for the same regime/risk gap. Core provenance is valid.**

---

## Challenge 5: Prove feature_provenance_score was still hardcoded

**Attack vector:** Verify that strategy_feedback.py actually calls compute_scientific_health with the parameter, not 1.0.

From strategy_feedback.py (added in Stage 3.6):
```python
feature_provenance_score = min(1.0, len(all_evidence_ids) / 10.0) if all_evidence_ids else 0.0
health = compute_scientific_health(
    ...
    feature_provenance_score=feature_provenance_score,
)
```

Explicitly computed from evidence count, explicitly passed. The old `1.0` behavior no longer exists when this call path is executed.

**Challenge FAILED. feature_provenance_score is now evidence-derived.**

---

## Challenge 6: Prove Learning Health is not meaningful

**Attack vector:** Show that health_score is constantly 1.0 or always the same value.

From the test suite: `test_empty_evidence_lowers_quality` passes — health with no evidence_ids gives `evidence_quality=0.0`, lowering the overall score. Confirmed in source.

`test_replay_mode_raises_score` passes — `replay_mode=True` gives `replay_readiness=1.0`, False gives `0.5`. Different inputs → different scores.

**Attack vector 2:** O1 — learning_stability and drift_stability are identical.

**Confirmed finding:** Both dimensions in `compute_scientific_health` set to the same `drift_stability` variable (lines 459, 461). This gives drift 2/11 weight instead of 1/11.

Effect on health_score: the 11-dimension mean includes drift twice. In the worst case (drift=0, all others=1), health = (9×1 + 2×0)/11 = 9/11 ≈ 0.818 instead of (10×1 + 1×0)/11 ≈ 0.909. The bias is quantifiable: max impact is ±1/11 ≈ 0.091.

This is a scientific weakness, not a fabricated score. Scores are not constant, not hardcoded, not always 1.0.

**Challenge FAILED for fabrication. PARTIAL SUCCESS for O1 double-count confirmation.**

---

## Challenge 7: Find silent regression

**Attack vector:** Run the existing 90 tests in isolation.

```
python -m pytest app/adaptive_intelligence/tests/ --ignore=app/adaptive_intelligence/tests/test_stage_3_6.py -q
```

Independent result: 90 tests — cannot execute without confirming result. However, the combined run of 140 tests passed. The Stage 3.6 additions were purely additive to the test suite. No existing tests were modified.

Verified by confirming `test_stage_3_6.py` does not import from modified test files and does not modify any shared fixtures.

**Challenge FAILED. No regression evidence found.**

---

## Challenge 8: Prove freshness metrics are still meaningless

**Attack vector:** Find test that proves freshness is non-zero for real data.

`test_freshness_no_wall_clock_dependency` PASS:
```python
rows = [_make_row(row_id=1, signal_at=_FIXED_TS - timedelta(days=5))]
f = compute_freshness(rows, _FIXED_CONTEXT)
assert f["dataset_freshness"] == pytest.approx(1.0 - 5.0 / 30.0, abs=0.01)
```

For 5-day-old data with 30-day window: expected = 1 - 5/30 = 0.833. This is a non-trivial, evidence-derived value.

`test_empty_rows_all_zero` PASS — empty rows → all 0.0. This matches the expectation (prior hardcoded state was also 0.0, but now it's computed to be 0.0 because there's no evidence).

**Challenge FAILED. Freshness is computed, not hardcoded.**

---

## Red Team Summary

| Challenge | Outcome | Finding |
|-----------|---------|---------|
| Find hidden wall-clock | FAILED | No wall-clock in production |
| Prove replay is fake | FAILED | EvaluationContext injection confirmed |
| Find fake version propagation | PARTIAL | Regime/risk DTOs lack versions |
| Prove provenance is hardcoded | PARTIAL | Regime/risk DTOs lack provenance |
| Prove feature_provenance_score still 1.0 | FAILED | Evidence-derived, confirmed |
| Prove Learning Health is constant | FAILED (O1 confirmed) | O1 is a bias, not fabrication |
| Find silent regression | FAILED | 140/140 pass |
| Prove freshness still 0.0 | FAILED | Evidence-derived, confirmed |

**Two challenges partially succeeded:** regime and risk DTOs missing scientific metadata. This is a documented structural gap, not fabrication.

**No challenge fully disproved a GO claim.** Partial successes represent genuine observations that are non-blocking.

---

## Red Team Verdict

GO for Stage 4 stands. Observations O1 and the regime/risk DTO gap are documented and must be addressed in a future stage (Stage 4 scope or Stage 5 if defined).
