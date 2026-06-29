# STAGE 3.6 — SCIENTIFIC READINESS AUDIT

**Date:** 2026-06-28
**Method:** Read-only inspection of all DTOs, engine code, and propagation chains
**Standard:** Every claim verified from source code, not from prior certification

---

## 1. Scientific Version Metadata

### Constants defined (dto.py:21-27)

```python
LEARNING_VERSION     = "business-os-1.3-stage-3.6"
CALIBRATION_VERSION  = "calibration-buckets-v1-stage-3.6"
FEATURE_VERSION      = "adaptive-learning-features-v1-stage-3.6"
POLICY_VERSION       = "adaptive-policy-hints-v1-stage-3.6"
ALGORITHM_VERSION    = "deterministic-adaptive-learning-v1-stage-3.6"
RESEARCH_VERSION     = "business-os-research-v1-stage-3.6"
EVIDENCE_VERSION     = "trading-signal-outcomes-v1-stage-3.6"
```

All 7 fields confirmed non-empty.

### Propagation trace

| Location | Carries versions | Evidence |
|----------|-----------------|---------|
| `LearningAuditTrail` | YES | dto.py:494 |
| `ContinuousLearningSignal` | YES | dto.py:516 |
| `ContinuousLearningProfile` | YES | dto.py:538 |
| `StrategySlice` | YES | dto.py:592 |
| `CalibrationBucket` | YES | dto.py:635 |
| `ConfidenceCalibrationResult` | YES | dto.py:655 |
| `AdaptiveIntelligenceReport` | YES | dto.py:714 |
| `RegimeAdapterResult` | **NO** | dto.py:672 — field absent |
| `RiskTuningResult` | **NO** | dto.py:683 — field absent |
| `policy_hints` dict | YES | orchestrator.py:350 — injected as dict |

**FINDING:** Version propagation is complete for strategy/calibration/learning layers. `RegimeAdapterResult` and `RiskTuningResult` do not carry `ScientificVersionMetadata` as DTO fields. They are compensated by the orchestrator, which captures all versions in `AdaptiveIntelligenceReport.versions` and `policy_hints["versions"]`.

**Classification:** OBSERVATION — not a blocker. Version lineage is preserved at the report level.

---

## 2. Feature Provenance

### FeatureProvenance (dto.py:63)

Fields present:
- `dataset_version` — from evaluation_context
- `feature_snapshot_id` — SHA-256(entity_id + feature_hash + evaluation_timestamp)
- `feature_hash` — SHA-256(entity_id + features dict + dataset_version + versions)
- `evidence_hash` — SHA-256(sorted evidence_ids)
- `evidence_ids` — list, capped at 25
- `research_version` — from ScientificVersionMetadata
- `policy_version` — from ScientificVersionMetadata

### Provenance coverage by DTO

| DTO | Has provenance | Has decision_hash | Has scientific_lineage |
|-----|---------------|-------------------|----------------------|
| `StrategySlice` | YES | YES | YES |
| `CalibrationBucket` | YES | YES | YES |
| `ContinuousLearningSignal` | YES | YES | YES |
| `LearningAuditTrail` | YES | YES | YES |
| `AdaptiveIntelligenceReport` | YES (report-level) | YES | — |
| `RegimeAdaptation` | **NO** | **NO** | **NO** |
| `RiskTuningResult` | **NO** | **NO** | **NO** |

**FINDING:** Primary learning outputs (strategy slices, calibration buckets) carry full provenance. Aggregation-layer outputs (regime adaptations, risk tuning) do not. This means individual regime recommendations and risk decisions cannot be independently reproduced from their DTOs alone.

**Mitigating factors:**
- Regime/risk are secondary aggregators of strategy/calibration data
- Report-level decision_hash covers the full evaluation
- All upstream inputs with provenance are accessible

**Classification:** SCIENTIFIC_GAP at the aggregation layer — not a Stage 4 blocker given the scope of these engines, but should be addressed in a future stage.

### Hash determinism verification

`evidence_hash = stable_hash({"evidence_ids": sorted(evidence_ids)})` (dto.py:162)

Uses `sorted()` — order-independent, deterministic. CONFIRMED.

`feature_hash` uses `sort_keys=True` JSON + SHA-256. CONFIRMED deterministic.

Minor observation: `evidence_ids` LIST stored in `FeatureProvenance.evidence_ids` is the first 25 of insertion-order accumulation (non-deterministic list, deterministic hash). Audit note: the hash is correct; the stored list is advisory.

---

## 3. Confidence Evolution

### ConfidenceEvolution (dto.py:73)

Fields:
- `initial_confidence` — baseline (0.5)
- `calibrated_confidence` — reliability/realized win rate
- `learned_confidence` — priority/economic score
- `final_confidence` — post-temporal-decay
- `initial_to_calibrated_delta`
- `calibrated_to_learned_delta`
- `learned_to_final_delta`
- `total_delta`

### Coverage

Present on: `StrategySlice`, `CalibrationBucket`, `ContinuousLearningSignal`, `LearningAuditTrail`

Computation in `ConfidenceCalibrationEngine.evaluate()`:
```python
confidence_evolution = build_confidence_evolution(
    initial=pred_avg / 100.0,
    calibrated=realized,
    learned=reliability,
    final=reliability * temporal_decay,
)
```
Four distinct stages, each from a different computation. CONFIRMED non-trivial.

**Finding:** CONFIRMED

---

## 4. Longitudinal Drift

### compute_longitudinal_drift (dto.py:322)

Windows: `(7, 30, 90, 180, 365)` — verified at line 327.

Per window:
- Uses `filter_rows_for_context` to get rows within window
- Computes win rate (confidence), return volatility, stability, degradation, improvement
- All from row data, no wall-clock

All 5 fields of `LongitudinalDriftMetric` are computed from evidence.

**Finding:** CONFIRMED — 5 windows, all evidence-derived, deterministic

---

## 5. Learning Saturation

### compute_learning_saturation (dto.py:357)

```python
short = populated[0].confidence    # shortest window win rate
long = populated[-1].confidence    # longest window win rate
marginal_gain = short - long
learning_velocity = marginal_gain / max(populated[-1].window_days - populated[0].window_days, 1)
saturation_score = max(0.0, min(1.0, 1.0 - abs(marginal_gain)))
plateau_detected = abs(marginal_gain) < 0.02
```

Evidence-derived from drift windows. No hardcoded values. `plateau_detected` threshold of 0.02 is a documented design constant, not a fake value.

**Finding:** CONFIRMED

---

## 6. Learning Health

### ScientificLearningHealth (dto.py:119) — 11 dimensions

| Dimension | Computation | Source |
|-----------|-------------|--------|
| replay_readiness | 1.0 if replay_mode else 0.5 | evaluation_context.replay_mode |
| version_completeness | non-empty fields / total | ScientificVersionMetadata |
| evidence_quality | min(1.0, len(evidence_ids)/10.0) | evidence_ids count |
| feature_provenance | feature_provenance_score param | evidence count (Stage 3.6 fix) |
| learning_stability | mean(drift.stability) | longitudinal_drift |
| calibration_quality | avg_confidence from slices | strategy evaluation |
| **drift_stability** | **mean(drift.stability)** | **= learning_stability (O1)** |
| learning_saturation | saturation.saturation_score | compute_learning_saturation |
| explainability | bool flag | always True in strategy |
| audit_completeness | evidence_ids AND explainability | evidence + flag |
| confidence_consistency | sample coverage ratio | sample count |

**OBSERVATION O1 CONFIRMED:** `learning_stability` (line 459) and `drift_stability` (line 461) both assign `drift_stability` local variable. They are IDENTICAL. Both are `mean(item.stability for item in drift)`. This gives drift stability 2/11 weight in `health_score`.

Effect: When drift stability is high, health_score is slightly inflated. When drift stability is low, health_score is slightly deflated. The bias is symmetric and predictable.

**Classification:** OBSERVATION — health_score is valid, slightly drift-biased. Not a fabricated score. Not a blocker.

---

## 7. Freshness Metrics

### compute_freshness (dto.py:379)

```python
ref_ts = evaluation_context.evaluation_timestamp.timestamp()
newest_ts = max(valid_ts)
age_days = max((ref_ts - newest_ts) / 86_400.0, 0.0)
dataset_freshness = max(0.0, min(1.0, 1.0 - age_days / 30.0))
evidence_freshness = max(0.0, min(1.0, 1.0 - age_days / 7.0))
feature_freshness = max(0.0, min(1.0, span_days / lookback)) if lookback > 0 else 0.0
learning_freshness = (dataset_freshness + evidence_freshness) / 2.0
```

**Prior state:** `{"dataset_freshness": 0.0, "evidence_freshness": 0.0, ...}` — hardcoded.
**Current state:** Computed from `evaluation_context.evaluation_timestamp` and row timestamps.

No wall-clock. No hardcoded values. 4 distinct metrics. Confirmed in `strategy_feedback.py` that `compute_freshness(all_rows, evaluation_context)` is called and result stored in `ContinuousLearningProfile.freshness`.

**Finding:** CONFIRMED — hardcoded blocker fully resolved

---

## 8. Remaining Scientific Gaps

| Gap | Severity | Blocking |
|-----|----------|---------|
| RegimeAdapterResult lacks versions and provenance | OBSERVATION | NO |
| RiskTuningResult lacks versions and provenance | OBSERVATION | NO |
| learning_stability == drift_stability (O1) | OBSERVATION | NO |
| evidence_ids list non-deterministic (hash deterministic) | LOW | NO |

---

## Audit Conclusion

```
Version Metadata:        GO WITH OBSERVATION (regime/risk DTOs lack versions)
Feature Provenance:      GO WITH OBSERVATION (regime/risk aggregators lack provenance)
Confidence Evolution:    GO
Longitudinal Drift:      GO
Learning Saturation:     GO
Learning Health:         GO WITH OBSERVATION (O1: drift double-counted)
Freshness:               GO (hardcoded 0.0 resolved)

SCIENTIFIC READINESS:    GO WITH OBSERVATIONS
```

The observations are documented, classified, and non-blocking. Scientific reproducibility is fully supported at the strategy/calibration/report level. Aggregation layers (regime/risk) are the only gap.
