# BUSINESS OS 1.5 — RANKING REPORT

**Version:** opportunity-ranking-v1-1.5  
**Date:** 2026-06-29  
**Status:** COMPLETE

---

## Ranking Strategies

| Strategy | Primary Key | Use Case |
|---|---|---|
| `BY_COMPOSITE` | composite_score | Default balanced ranking |
| `BY_CONFIDENCE` | confidence | Most reliable opportunities first |
| `BY_NOVELTY` | novelty | Newest signals first |
| `BY_IMPACT` | impact | Highest impact first |
| `BY_URGENCY` | urgency | Most time-sensitive first |
| `BY_FRESHNESS` | freshness | Most recent evidence first |

---

## Tiebreak Rule

```
sort key = (-primary_score, -confidence, opportunity_id)
```

Lexicographic `opportunity_id` tiebreak ensures determinism even when multiple opportunities share identical scores.

---

## Explainability

After ranking, every opportunity receives:

```
"Rank #N by strategy 'by_composite': composite=0.XXX, confidence=0.XXX, novelty=0.XXX, impact=0.XXX."
```

This rationale is stored in `opportunity.explanation.ranking_rationale`.

---

## Properties

- **Deterministic**: Same input → same ranked list across all runs
- **Explainable**: Every rank has a textual rationale with the key scores
- **Reproducible**: Strategy is embedded in `OpportunityReport.ranking_strategy`
- **Stable**: Tiebreak by `opportunity_id` (not insertion order)

---

## Validation

| Test | Result |
|---|---|
| Returns same count | PASS |
| BY_COMPOSITE sorted descending | PASS |
| BY_CONFIDENCE sorted descending | PASS |
| Deterministic | PASS |
| Annotates ranking_rationale | PASS |
| Empty input → [] | PASS |
| All strategies produce valid ranking | PASS |
| Stable tiebreak | PASS |
