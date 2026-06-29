# STAGE 3.6 — AUDIT OF AUDIT

**Date:** 2026-06-28
**Method:** Second independent pass using a different inspection methodology
**Approach:** Trace backwards from outputs to inputs, instead of forward from inputs to outputs

---

## Methodology Contrast

**First audit (STAGE_3_6_SCIENTIFIC_AUDIT.md):**
Forward trace — starts at constants and DTOs, follows propagation to outputs.

**This audit:**
Backward trace — starts at `AdaptiveIntelligenceReport` outputs, traces each field back to its source.

---

## 1. Backward Trace: `report.decision_hash`

**Found at:** orchestrator.py:415 — `report = AdaptiveIntelligenceReport(..., decision_hash=report_hash)`

**report_hash** ← `build_decision_hash(evaluation_context=context, versions=versions, provenance=report_provenance, entity_id="adaptive_intelligence_report", recommendation=overall_rec)` (orchestrator.py:379)

**report_provenance** ← `build_feature_provenance(evaluation_context=context, entity_id="adaptive_intelligence_report", features={"overall_recommendation": ..., "risk_level": ..., "strategy_outcomes": ..., "calibration_outcomes": ...}, evidence_ids=..., versions=versions)` (orchestrator.py:362)

**context** ← if `strategy.continuous_learning.evaluation_context` exists (line 296), use that; else `self._evaluation_context or _fallback_context(self._lookback_days)` (line 285)

**Chain:** report.decision_hash ← build_decision_hash ← build_feature_provenance ← EvaluationContext ← (injected or derived from rows)

**Backward trace CLEAN.** No wall-clock. No hardcoded intermediate values.

---

## 2. Backward Trace: `report.continuous_learning.freshness`

**Found at:** strategy_feedback.py — `ContinuousLearningProfile(freshness=freshness, ...)`

**freshness** ← `compute_freshness(all_rows, evaluation_context)` (strategy_feedback.py)

**compute_freshness** reads `evaluation_context.evaluation_timestamp` and `_row_timestamp(row)` for each row.

**Chain:** freshness ← compute_freshness ← evaluation_context.evaluation_timestamp ← (injected or derived from max(row timestamps))

**Backward trace CLEAN.** No hardcoded 0.0. Confirmed resolved.

---

## 3. Backward Trace: `report.continuous_learning.scientific_health.health_score`

**Found at:** strategy_feedback.py — `ContinuousLearningProfile(scientific_health=health, ...)`

**health** ← `compute_scientific_health(evaluation_context, versions, evidence_ids=all_evidence_ids, drift=drift, saturation=saturation, explainability_present=True, calibration_quality=avg_confidence, confidence_consistency=coverage_confidence, feature_provenance_score=feature_provenance_score)`

**feature_provenance_score** ← `min(1.0, len(all_evidence_ids) / 10.0)` — evidence-derived

**drift** ← `compute_longitudinal_drift(all_rows, evaluation_context)` — evidence-derived

**saturation** ← `compute_learning_saturation(drift)` — derived from drift

**avg_confidence** ← `sum(signal.current_confidence) / len(signals)` — derived from slice analysis

**Second audit finding on O1:** Confirmed independently. In `compute_scientific_health`:
- `drift_stability` is computed once as `sum(item.stability) / len(drift)`
- Both `learning_stability` and `drift_stability` keys in `dimensions` dict are assigned this same value

This is independently verified — not an artefact of the first audit.

**Chain:** health_score ← mean(11 dimensions) — all evidence-derived, with O1 double-count. CONFIRMED.

---

## 4. Backward Trace: `slice.versions.learning_version`

**Found at:** strategy_feedback.py:439 — `StrategySlice(versions=versions, ...)`

**versions** ← `ScientificVersionMetadata()` (strategy_feedback.py:298)

**ScientificVersionMetadata.learning_version** ← `LEARNING_VERSION = "business-os-1.3-stage-3.6"` (dto.py:21)

**Chain:** slice.versions.learning_version ← ScientificVersionMetadata ← string constant. CONFIRMED.

---

## 5. Backward Trace: `RegimeAdaptation` fields

**Found at:** regime_adapter.py:157 — `adaptations.append(RegimeAdaptation(regime=..., signal=..., symbol=..., timeframe=..., sample_size=..., win_rate=..., expectancy=..., recommendation=..., reason=...))`

**versions field:** ABSENT in `RegimeAdaptation` constructor call and DTO definition.
**provenance field:** ABSENT.
**decision_hash field:** ABSENT.
**evidence_ids field:** ABSENT.

**Independent confirmation of the regime DTO gap.** Same finding as the first audit but reached by backward trace. The gap is real.

---

## 6. Agreement/Disagreement Matrix

| Claim | First Audit | This Audit | Agreement |
|-------|-------------|------------|-----------|
| No wall-clock in production | GO | GO | AGREE |
| EvaluationContext injection works | GO | GO | AGREE |
| Version propagation — strategy/calibration | GO | GO | AGREE |
| Version propagation — regime/risk DTOs | OBSERVATION (gap) | OBSERVATION (gap) | AGREE |
| Feature provenance on slices | GO | GO | AGREE |
| Feature provenance on regime/risk | OBSERVATION (gap) | OBSERVATION (gap) | AGREE |
| Freshness is computed (not hardcoded) | GO | GO | AGREE |
| Health score is evidence-derived | GO | GO | AGREE |
| O1: learning_stability = drift_stability | CONFIRMED | CONFIRMED | AGREE |
| Longitudinal drift: 5 windows | GO | GO | AGREE |
| Learning saturation: evidence-derived | GO | GO | AGREE |
| Confidence evolution: 4 stages | GO | GO | AGREE |
| Architecture: single engines | GO | GO | AGREE |
| 140 tests passing | CONFIRMED | CONFIRMED | AGREE |

**No disagreements between the two audits.**

---

## 7. Additional Finding From Backward Trace

**`temporal_decay` in ConfidenceCalibrationEngine:**

```python
temporal_decay = _clamp(1.0 - (self._lookback_days / 365.0), lower=0.25)
```

This uses `lookback_days` as a proxy for the temporal distance from data to present. It does not use actual row timestamps to compute age. For `lookback_days=30`: decay = 0.918. For `lookback_days=365`: decay = 0.25 (minimum).

**Assessment:** This is a design approximation, not a wall-clock dependency. `lookback_days` is an input parameter, making this deterministic. The approximation means that calibration buckets with longer lookback windows have lower effective temporal weight — which is a reasonable model assumption. Not a bug, not a fake value.

**Classification:** DESIGN_CHOICE — backward trace produced a finding the forward audit did not specifically highlight. No impact on certification.

---

## Audit of Audit Conclusion

Both audits independently reached the same conclusions via different methodologies. No contradictions. No hidden findings that disprove the first audit.

**Combined certification basis:** both forward and backward traces confirm Stage 3.6 GO.

**One additional finding:** `temporal_decay` approximation in calibration — documented as DESIGN_CHOICE.
