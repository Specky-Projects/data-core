# BUSINESS OS 1.3 — STAGE 4 — ADAPTIVE HEALTH REPORT

**Date:** 2026-06-28
**Stage:** 4 — Foundation

---

## Health Model Evolution

Stage 3.6 introduced `ScientificLearningHealth` with 11 evidence-derived dimensions.

Stage 4 introduces `AdaptiveIntelligenceHealth` — a 16-dimension extended model.

---

## Stage 3.6 Dimensions (Preserved, O1-Fixed)

| Dimension | Measurement | Fix in Stage 4 |
|-----------|-------------|----------------|
| replay_readiness | 1.0 if evaluation_context.replay_mode else 0.5 | None |
| version_completeness | fraction of non-empty version fields | None |
| evidence_quality | min(1.0, len(evidence_ids) / 10.0) | None |
| feature_provenance | min(1.0, len(all_evidence_ids) / 10.0) | None |
| **learning_stability** | **1.0 - std_dev(window_confidences) / 0.2** | **O1 fix** |
| calibration_quality | mean(current_confidence) across discovery signals | None |
| drift_stability | mean(drift[i].stability) | None (measurement preserved) |
| learning_saturation | saturation_score from LearningSaturation | None |
| explainability | 1.0 if explainability_present else 0.0 | None |
| audit_completeness | 1.0 if evidence_ids and explainability_present else 0.5 | None |
| confidence_consistency | min(1.0, total_samples / 100.0) | None |

Note: In Stage 3.6, `learning_stability` was incorrectly set to `drift_stability`. In Stage 4, it measures cross-window confidence consistency — a distinct and orthogonal property.

---

## Stage 4 New Dimensions

| Dimension | Formula | Range |
|-----------|---------|-------|
| recommendation_quality | (precision + recall) / 2 | [0, 1] |
| learning_effectiveness | max(0, learning_impact) | [0, 1] |
| strategy_stability | mean(si.recommendation_consistency) | [0, 1] |
| confidence_accuracy | decision_quality.stability | [0, 1] |
| decision_quality_score | (precision + stability + calibration_effectiveness) / 3 | [0, 1] |

**health_score** = mean(all 16 dimensions)

---

## Health Score Properties

1. **Evidence-derived**: All 16 dimensions computed from historical outcome data
2. **No hardcoded constants**: health_score responds to actual evidence changes
3. **Bounded**: All dimensions in [0, 1], health_score in [0, 1]
4. **Deterministic**: Same evidence inputs → same health_score
5. **Interpretable**: Each dimension has a clear semantic meaning

---

## Expected Ranges

| Scenario | Expected health_score |
|----------|----------------------|
| No evidence | ~0.30 (evidence_quality=0, feature_provenance=0, etc.) |
| Sparse evidence (n=5) | ~0.45 |
| Moderate evidence (n=30) | ~0.65 |
| Rich evidence (n=100+) with good signals | ~0.80+ |

Stage 4 health_score will typically be lower than Stage 3.6 health_score for the same evidence, because the 5 new dimensions start at 0.0 when there are no slices. This is expected and correct — Stage 4 measures more dimensions, so a higher score requires more evidence.

---

## Relationship to ScientificLearningHealth

`AdaptiveIntelligenceHealth` does not replace `ScientificLearningHealth`. Both are stored:

- `ContinuousLearningProfile.scientific_health` — 11-dim model (Stage 3.6, backward compat)
- `ContinuousLearningProfile.adaptive_health` — 16-dim model (Stage 4)

`compute_adaptive_health(scientific_health, decision_quality, strategy_intelligence)` uses the 11-dim score as the foundation and extends it. It does not recompute the 11 Stage 3.6 dimensions — it inherits them directly from `scientific_health`.
