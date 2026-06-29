# BUSINESS OS 1.5 — SCORING REPORT

**Version:** opportunity-scoring-v1-1.5  
**Date:** 2026-06-29  
**Status:** COMPLETE

---

## 10-Dimension Evidence-Derived Score

Every dimension derives from observable evidence. No arbitrary weights.

| Dimension | Derivation |
|---|---|
| `novelty` | Carried from discovery (`0.2 + 0.1 × source_count`) |
| `evidence_strength` | `min(1.0, evidence_count / 10.0)` |
| `source_diversity` | `min(1.0, source_type_count / 4.0)` |
| `growth_velocity` | `min(1.0, (evidence + correlations) / 15.0)` |
| `confidence` | From discovery formula |
| `risk` | `1.0 - confidence` (inverse) |
| `market_impact` | Derived from `opp.impact` field |
| `strategic_relevance` | `confidence × 0.6 + source_diversity × 0.4` |
| `consistency` | `evidence_strength × 0.5 + source_diversity × 0.5` |
| `freshness` | Half-life decay from evidence timestamps (30-day half-life), or 0.05 if no timestamps |

---

## Composite Score

```
composite_score = mean(novelty, evidence_strength, source_diversity,
                       growth_velocity, confidence, market_impact,
                       strategic_relevance, consistency, freshness)
```

Risk is NOT included in composite (it is a penalty signal, not a positive dimension).

---

## Evidence Exposure

Every `OpportunityScore` carries `evidence_ids: list[str]` — the first 10 evidence IDs that contributed to the score. Every score is fully traceable.

---

## Validation

| Test | Result |
|---|---|
| Returns OpportunityScore | PASS |
| composite_score bounded [0,1] | PASS |
| All 10 dimensions bounded [0,1] | PASS |
| Deterministic | PASS |
| evidence_ids present | PASS |
| More evidence → higher evidence_strength | PASS |
| Versions set on score | PASS |
