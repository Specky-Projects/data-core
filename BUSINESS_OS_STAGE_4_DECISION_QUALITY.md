# BUSINESS OS 1.3 — STAGE 4 — ADAPTIVE DECISION QUALITY

**Date:** 2026-06-28
**Stage:** 4 — Foundation

---

## Overview

Adaptive Decision Quality tracks how well the learning system translates historical evidence into correct recommendations.

Three new capabilities:

1. **DecisionQualityMetric** — precision, recall, stability of the recommendation system
2. **RecommendationEvolution** — per-slice direction (improved/degraded/stable) and maturity
3. **StrategyIntelligence** — per-slice adaptive confidence and recommendation consistency

---

## DecisionQualityMetric

Computed by `compute_decision_quality(slices)`.

### Precision

`fraction of BOOST/KEEP slices with win_rate ≥ 0.5`

Measures: when the system recommends a slice for execution, how often does the evidence support it?
- High precision → promoted slices tend to be actually good
- Low precision → the system is recommending slices without adequate win-rate evidence

### Recall

`fraction of high-win slices (win_rate ≥ 0.5) that received BOOST/KEEP`

Measures: when a slice has strong evidence, does the system capture it?
- High recall → the system identifies most strong performers
- Low recall → strong performers are being throttled or observed unnecessarily

### Stability

`fraction of slices where recommendation aligns with win_rate direction`

- BOOST/KEEP for win_rate ≥ 0.5 → consistent
- THROTTLE/DISABLE/OBSERVE_ONLY for win_rate < 0.5 → consistent

### Calibration Effectiveness

`max(0, 1.0 - mean(|total_delta|) / 0.5)`

Measures how much the learning pipeline modifies confidence. High effectiveness = small adjustments (already calibrated). Low = large adjustments (system was initially miscalibrated).

### Learning Impact

`mean(confidence_evolution.total_delta) across slices`

Positive → learning increased overall confidence (system is finding signal).
Negative → learning decreased overall confidence (system is correctly becoming more conservative).
Near zero → learning is stable.

---

## RecommendationEvolution

Per-slice tracking computed by `compute_recommendation_evolution(slices)`.

### Maturity Classification

| Maturity | Condition | Interpretation |
|----------|-----------|----------------|
| bootstrap | sample_size < 10 | Insufficient data — any recommendation is provisional |
| developing | 10 ≤ sample_size < 30 | Growing evidence — recommendation can shift |
| mature | sample_size ≥ 30 | Reliable evidence base — recommendation is stable |

### Direction Classification

| Direction | Condition |
|-----------|-----------|
| improved | total_delta > 0.05 — confidence improved |
| degraded | total_delta < -0.05 — confidence degraded |
| stable | |total_delta| ≤ 0.05 — marginal change |
| insufficient_data | no confidence_evolution available |

---

## StrategyIntelligence

Per-slice computed by `compute_strategy_intelligence(slices)`.

### maturity_score

`min(1.0, sample_size / MIN_SAMPLE_FOR_BOOST)` where MIN_SAMPLE_FOR_BOOST = 30.

Score = 0 for new slices. Approaches 1.0 as evidence accumulates. Used to weight adaptive_confidence.

### adaptive_confidence

`win_rate * maturity_score + 0.5 * (1.0 - maturity_score)`

For immature slices (low maturity_score), adaptive_confidence is pulled toward 0.5 (neutral). As maturity grows, adaptive_confidence converges to the actual win_rate.

This prevents over-trusting a 0.8 win_rate from 3 trades.

### recommendation_consistency

Measures alignment between recommendation and evidence:
- 1.0: BOOST/KEEP with win_rate ≥ 0.5 (aligned)
- 1.0: THROTTLE/DISABLE with win_rate < 0.4 (aligned)
- 0.8: OBSERVE_ONLY (conservative but safe)
- Scaled: `max(0.0, 1.0 - |win_rate - 0.5| * 2.0)` for misaligned cases

---

## Integration Point

All three outputs are stored in `ContinuousLearningProfile`:

```python
profile.adaptive_decision_quality  # DecisionQualityMetric
profile.recommendation_evolution   # list[RecommendationEvolution]
profile.strategy_intelligence      # list[StrategyIntelligence]
```

And aggregated into `AdaptiveIntelligenceHealth.decision_quality_score`, `recommendation_quality`, `learning_effectiveness`, `strategy_stability`, `confidence_accuracy`.
