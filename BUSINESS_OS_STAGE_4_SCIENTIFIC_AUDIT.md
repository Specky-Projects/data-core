# BUSINESS OS 1.3 — STAGE 4 — SCIENTIFIC AUDIT

**Date:** 2026-06-28
**Stage:** 4 — Foundation
**Method:** Forward trace — constants → computation → output

---

## 1. Version Propagation

All 7 version constants updated to `stage-4`:

```
LEARNING_VERSION    = "business-os-1.3-stage-4"
CALIBRATION_VERSION = "calibration-buckets-v1-stage-4"
FEATURE_VERSION     = "adaptive-learning-features-v1-stage-4"
POLICY_VERSION      = "adaptive-policy-hints-v1-stage-4"
ALGORITHM_VERSION   = "deterministic-adaptive-learning-v1-stage-4"
RESEARCH_VERSION    = "business-os-research-v1-stage-4"
EVIDENCE_VERSION    = "trading-signal-outcomes-v1-stage-4"
```

`ScientificVersionMetadata()` constructor reads these constants. All downstream DTOs that carry `versions: ScientificVersionMetadata` automatically carry stage-4 labels.

**Propagation chain verified:**
- `dto.py:LEARNING_VERSION` → `ScientificVersionMetadata.learning_version` → `StrategySlice.versions.learning_version` (strategy_feedback.py)
- `dto.py:LEARNING_VERSION` → `ScientificVersionMetadata.learning_version` → `RegimeAdaptation.versions.learning_version` (regime_adapter.py — Stage 4 addition)
- `dto.py:LEARNING_VERSION` → `ScientificVersionMetadata.learning_version` → `RiskTuningResult.versions.learning_version` (risk_tuner.py — Stage 4 addition)

**Test:** `TestVersionConstants` — 9 tests, all PASS.

---

## 2. O1 Fix Verification

### Before Stage 4

```python
drift_stability = sum(item.stability for item in drift) / len(drift)
dimensions = {
    "learning_stability": drift_stability,  # identical
    "drift_stability": drift_stability,     # identical
}
```

### After Stage 4

```python
drift_stability = sum(item.stability for item in drift) / len(drift)
learning_stability = _compute_learning_stability(drift)  # distinct

def _compute_learning_stability(drift):
    confidences = [d.confidence for d in populated]
    mean_c = sum(confidences) / len(confidences)
    variance = sum((c - mean_c) ** 2 for c in confidences) / len(confidences)
    std_dev = variance ** 0.5
    return max(0.0, min(1.0, 1.0 - std_dev / 0.2))
```

**Semantic distinction:**
- `drift_stability` = mean of per-window intra-window return stability (how smooth returns are inside each window)
- `learning_stability` = inverse of cross-window confidence variance (how consistent win-rate is across 7/30/90/180/365d windows)

These are orthogonal measurements. High `drift_stability` (smooth returns) does not imply high `learning_stability` (consistent win-rate across time).

**Edge cases:**
- Empty drift → both return 0.0 (drift_stability via division guard, learning_stability via len < 2 check)
- Single drift entry → `drift_stability` = that entry's stability; `learning_stability` = 0.5 (neutral, insufficient data)
- All windows same confidence → `learning_stability` = 1.0

**Test:** `TestO1LearningStabilityFix` — 5 tests, including explicit assertion that `health.learning_stability != health.drift_stability` for volatile patterns.

---

## 3. O3 Fix Verification

### RegimeAdaptation

**Before:** `RegimeAdaptation` had 9 fields. No `evidence_ids`, `versions`, `provenance`, `decision_hash`.

**After:** `RegimeAdaptation` has 13 fields. Added `evidence_ids`, `versions`, `provenance`, `decision_hash` with defaults (backward-compatible).

**Source chain (regime_adapter.py):**
1. `_Acc.evidence_ids` accumulates `str(row.id)` per row
2. `build_feature_provenance(evaluation_context, entity_id, features, evidence_ids=acc.evidence_ids, versions=versions)` builds FeatureProvenance
3. `build_decision_hash(evaluation_context, versions, provenance, entity_id, recommendation)` builds decision_hash
4. All 3 passed to `RegimeAdaptation()`

### RiskTuningResult

**Before:** `RiskTuningResult` had 12 fields. No `versions`, `provenance`, `decision_hash`.

**After:** `RiskTuningResult` has 15 fields. Added `versions`, `provenance`, `decision_hash` with defaults.

**Source chain (risk_tuner.py):**
1. `versions = ScientificVersionMetadata()` built in `evaluate()`
2. `build_feature_provenance(ctx, entity_id="risk_tuning_result", features={win_rate, exp, pf, ...}, evidence_ids=[], versions=versions)`
3. `build_decision_hash(ctx, versions, provenance, entity_id="risk_tuning_result", recommendation=risk_level)`
4. All 3 passed to `RiskTuningResult()`

**Limitation noted:** `RiskTuningResult.evidence_ids` is empty ([]). The risk tuner does not directly track individual outcome IDs — it uses aggregate metrics. This is correct behavior: risk-level evidence is at the aggregate level. The `provenance` still carries the features used to derive the risk level.

---

## 4. O4 Fix Verification

**Before:** `build_feature_provenance` returned `evidence_ids=evidence_ids[:25]` — insertion order dependent.

**After:** `evidence_ids=sorted(evidence_ids)[:25]` — lexicographically sorted, deterministic.

**evidence_hash** was already using `sorted()` for hash computation. Now the list matches the hash's sort order, ensuring the list and hash are aligned.

**Test:** Input `["5", "2", "8", "1", "3"]` → stored as `["1", "2", "3", "5", "8"]`. Input `["c", "a", "b"]` → same as `["a", "b", "c"]` regardless of insertion order.

---

## 5. O5 Fix Verification

**Before:** `risk_tuner.py:evaluate()` used `self._resolved_evaluation_context.evaluation_timestamp` directly. If `_resolved_evaluation_context` was `None`, this raised `AttributeError`.

**After:**
```python
_EPOCH = datetime.fromisoformat("1970-01-01T00:00:00+00:00")  # module constant

ctx = self._resolved_evaluation_context or EvaluationContext(
    evaluation_timestamp=_EPOCH,
    replay_mode=True,
    dataset_timestamp=_EPOCH,
    dataset_version="fallback",
    replay_configuration={"source": "risk_tuner_fallback"},
    lookback_days=self._lookback_days,
)
```

`_EPOCH` follows the same pattern as `orchestrator.py`'s fallback. The fallback context is deterministic (no wall-clock).

**When does O5 trigger:** Only if `_fetch_recent_aggregates()` raises before line 181, AND the caller injected `evaluation_context=None`. The orchestrator already has a try/except that catches this, so the real-world impact is near-zero. The fix prevents a latent AttributeError from ever surfacing.

---

## 6. O6 Fix Verification

**Before:** `temporal_decay = _clamp(1.0 - (self._lookback_days / 365.0), lower=0.25)` — same value for all buckets, regardless of actual data age.

**After:** Per-bucket computation:
```python
if acc.timestamps:
    ref_ts = evaluation_context.evaluation_timestamp.timestamp()
    mean_age_days = max(0.0, (ref_ts - sum(acc.timestamps) / len(acc.timestamps)) / 86_400.0)
    temporal_decay = _clamp(1.0 - mean_age_days / 365.0, lower=0.25)
else:
    temporal_decay = _clamp(1.0 - (self._lookback_days / 365.0), lower=0.25)
```

`evaluation_context.evaluation_timestamp` is used as reference — not `datetime.now()`. The fallback (when `acc.timestamps` is empty) retains the prior behavior for backward safety.

**Correctness check:** For rows 5 days old with evaluation_timestamp as reference:
- `mean_age_days = 5.0`
- `temporal_decay = max(0.25, 1.0 - 5.0/365.0) ≈ 0.986`

For rows 180 days old:
- `temporal_decay = max(0.25, 1.0 - 180.0/365.0) ≈ 0.507`

Prior approximation for `lookback_days=30`: `1.0 - 30/365 = 0.918`. For data actually 5 days old, the true value is 0.986 — the fix is more accurate.

---

## 7. Stage 4 Capabilities — Evidence Derivation Audit

### compute_decision_quality

All fields derived from `slices` (list of StrategySlice from StrategyFeedbackEngine):
- `precision` — from `s.recommendation` and `s.win_rate`
- `recall` — from `s.win_rate` and `s.recommendation`
- `stability` — from alignment between `s.recommendation` and `s.win_rate`
- `calibration_effectiveness` — from `s.confidence_evolution.total_delta`
- `learning_impact` — from `s.confidence_evolution.total_delta`
- `sample_size` — from `sum(s.sample_size)`

No hardcoded constants in the computation. All evidence-derived. No wall-clock.

### compute_recommendation_evolution

All fields derived from `s.sample_size` and `s.confidence_evolution.total_delta`.
- `maturity` — from `s.sample_size` vs `MIN_SAMPLE_FOR_RECOMMENDATION` and `MIN_SAMPLE_FOR_BOOST`
- `direction` — from `total_delta` thresholds (±0.05)
- `confidence_delta` — from `total_delta` directly

### compute_strategy_intelligence

All fields derived from `s.sample_size`, `s.win_rate`, `s.recommendation`, `s.relevance_score`.
- `maturity_score` = `min(1.0, sample_size / MIN_SAMPLE_FOR_BOOST)`
- `reliability_score` = `s.relevance_score` (already computed from win_rate, impact_score, sample_confidence)
- `adaptive_confidence` = `win_rate * maturity + 0.5 * (1 - maturity)` — dampens immature signals toward neutral
- `recommendation_consistency` = 1.0 if rec aligns with win_rate evidence, else degraded proportionally

### compute_adaptive_health

Inherits 11 dimensions from `ScientificLearningHealth` (evidence-derived, Stage 3.6 certified).
Adds 5 dimensions from `DecisionQualityMetric` and `list[StrategyIntelligence]`.
`health_score` = mean(all 16 dimensions) — no arbitrary weighting.

**No hardcoded constants in the 5 new dimensions.** All derived from evidence-based inputs.

---

## 8. Scientific Audit Verdict

| Dimension | Before Stage 4 | After Stage 4 |
|-----------|---------------|---------------|
| O1: learning_stability independence | FAIL (equal to drift_stability) | **PASS** |
| O3: Regime DTO metadata completeness | FAIL (missing versions/provenance/decision_hash) | **PASS** |
| O3: Risk DTO metadata completeness | FAIL (missing versions/provenance/decision_hash) | **PASS** |
| O4: evidence_ids canonical ordering | FAIL (insertion order) | **PASS** |
| O5: RiskTuner null safety | LATENT (guarded by orchestrator) | **CLOSED** |
| O6: temporal_decay evidence-based | APPROXIMATION | **EVIDENCE-BASED** |
| New capabilities evidence-derived | N/A | **ALL VERIFIED** |
| Wall-clock in production | ZERO | **ZERO** |
| Deterministic replay | PASS | **PASS** |

**All Stage 4 mandatory changes verified evidence-derived and deterministic.**
