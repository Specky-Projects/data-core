# BUSINESS OS 1.5 — OPPORTUNITY HEALTH REPORT

**Version:** opportunity-health-v1-1.5  
**Date:** 2026-06-29  
**Status:** COMPLETE

---

## 10-Dimension Health Model

Every metric derives from evidence in the opportunity set.

| Dimension | Derivation |
|---|---|
| `evidence_quality` | Mean `score.evidence_strength` across all opportunities |
| `freshness` | Mean `score.freshness` |
| `confidence` | Mean `confidence` |
| `consistency` | Mean `score.consistency` |
| `coverage` | Fraction of opportunities with ≥ 2 sources OR ≥ 1 correlation |
| `source_diversity` | Mean `score.source_diversity` |
| `market_activity` | Mean `score.market_impact` |
| `historical_stability` | Fraction of opportunities with evolution history |
| `novelty` | Mean `novelty` |
| `explainability` | Fraction with non-empty `explanation.why_exists` |

```
health_score = mean(all 10 dimensions)
```

---

## Empty Input Behavior

When no opportunities exist, all dimensions = 0.0 and `health_score = 0.0`.

---

## Versions

`OpportunityHealth.versions` carries the full `OpportunityVersionMetadata`, making health reports fully traceable across versions.

---

## Validation

| Test | Result |
|---|---|
| Empty → health_score=0.0 | PASS |
| Non-empty → bounded [0,1] | PASS |
| All 10 dimensions bounded | PASS |
| opportunity_count matches | PASS |
| explainability from explanations | PASS |
| Versions set | PASS |
| Deterministic | PASS |
