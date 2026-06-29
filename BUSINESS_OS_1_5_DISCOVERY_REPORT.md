# BUSINESS OS 1.5 — DISCOVERY REPORT

**Version:** opportunity-discovery-v1-1.5  
**Date:** 2026-06-29  
**Status:** COMPLETE

---

## Discovery Methods

### Method 1: Cross-Source Entity Presence (`discover_from_knowledge_items`)

An entity mentioned across ≥ `min_source_count` (default: 2) independent sources becomes an opportunity candidate.

Pipeline per entity:
1. Collect all KnowledgeItems containing the entity
2. Count distinct source IDs
3. If `|sources| ≥ min_source_count` → create Opportunity
4. Assign `OpportunityType` via heuristic (topics + entity types)
5. Build `OpportunityProvenance` with all contributing item IDs
6. Compute `OpportunityExplanation.why_exists` with source list

Confidence formula:
```
confidence = min(1.0, 0.3 + 0.15 × source_count + 0.05 × evidence_count)
```

### Method 2: Cross-Source Correlation Signals (`discover_from_correlations`)

`KnowledgeCorrelation` with signal `CROSS_SOURCE_CONVERGENCE` or `SUSTAINED_ATTENTION` maps directly to an opportunity.

Confidence formula:
```
confidence = correlation.strength × 0.8 + 0.1
```

---

## Deduplication

After both discovery paths run, opportunities are deduplicated by `opportunity_id`. The first occurrence wins. The merge happens in the orchestrator before scoring.

---

## Type Classification Heuristic

| Condition | Type |
|---|---|
| entity_type=TECHNOLOGY or topic in {ml, ai, llm, gpu, cloud} | TECHNOLOGY |
| entity_type=REPOSITORY or topic=open_source | OPEN_SOURCE |
| topic in {research, paper, arxiv} | RESEARCH |
| entity_type=PRODUCT | PRODUCT |
| topic=infrastructure | INFRASTRUCTURE |
| Otherwise | UNKNOWN |

---

## Determinism

- `opportunity_id` is derived from `title.lower() + domain.lower() + type.value`
- Same KnowledgeReport → same discovery output every time
- No randomness, no wall-clock in discovery logic

---

## Validation

| Test | Result |
|---|---|
| Returns list | PASS |
| Empty input → [] | PASS |
| IDs deterministic | PASS |
| Has provenance | PASS |
| Confidence bounded [0,1] | PASS |
| has why_exists explanation | PASS |
| No duplicate IDs | PASS |
| created_at from context | PASS |
