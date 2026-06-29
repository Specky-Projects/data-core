# BUSINESS OS 1.5 — LIFECYCLE REPORT

**Version:** opportunity-lifecycle-v1-1.5  
**Date:** 2026-06-29  
**Status:** COMPLETE

---

## Lifecycle Stages

```
NEW → EARLY → GROWING → MATURE → DECLINING → ARCHIVED
```

---

## Transition Rules (Deterministic)

All transitions are driven by evidence-derived metrics. No wall-clock.

| Stage | Condition |
|---|---|
| `ARCHIVED` | confidence < 0.05 OR evidence_count == 0 |
| `DECLINING` | composite_score < 0.15 |
| `MATURE` | confidence ≥ 0.7 AND sources ≥ 4 AND evidence ≥ 10 |
| `GROWING` | confidence ≥ 0.45 AND sources ≥ 3 AND evidence ≥ 5 |
| `EARLY` | confidence ≥ 0.25 AND sources ≥ 2 |
| `NEW` | Otherwise |

Rules are checked in priority order (ARCHIVED → DECLINING → MATURE → GROWING → EARLY → NEW).

---

## Evolution Snapshots

Every lifecycle advancement records an `OpportunityEvolutionSnapshot`:
- `snapshot_id = _k_stable_hash({"opp": opportunity_id, "ts": evaluation_timestamp})`
- Records: confidence, priority, composite_score, lifecycle_stage, evidence_count, source_count, entity_count
- Appended to `opportunity.evolution_history`
- `opportunity.updated_at` set to `evaluation_context.evaluation_timestamp`

---

## Lifecycle Rationale

Every transition (or stable stage) produces an explanation:
```
"Stage transitioned from NEW → GROWING. Confidence=0.450, score=0.387, evidence=6, sources=3."
```
or:
```
"Stage stable: GROWING. Confidence=0.450, score=0.387."
```

---

## Validation

| Test | Result |
|---|---|
| Low confidence → not MATURE | PASS |
| No evidence → ARCHIVED | PASS |
| advance_lifecycle records snapshot | PASS |
| Snapshot has correct timestamp | PASS |
| updated_at set from context | PASS |
| Lifecycle rationale annotated | PASS |
| Deterministic transitions | PASS |
