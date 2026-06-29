# BUSINESS OS 1.4 — CROSS-SOURCE CORRELATION REPORT

**Version:** cross-source-correlation-v1-1.4  
**Date:** 2026-06-29  
**Status:** COMPLETE

---

## Two Correlation Algorithms

### 1. Cross-Source Entity Correlation (`compute_cross_source_correlations`)

Detects entities appearing across multiple sources within a time window.

- Time window: items where `published_at >= evaluation_timestamp - window_days * 86400`
- Per entity: count distinct sources, count total evidence appearances
- Minimum thresholds: `min_sources=2`, `min_mentions=2`
- Signal classification:
  - `CROSS_SOURCE_CONVERGENCE`: ≥ 3 sources
  - `SUSTAINED_ATTENTION`: ≥ 5 total mentions
  - `INCREASING_MENTIONS`: default

### 2. Entity Co-Occurrence (`compute_entity_co_occurrence`)

Detects entity pairs co-occurring frequently within the same items.

- Per item: all entity pairs → count co-occurrences
- Minimum: `min_co_occurrence=2`
- Signal: `INCREASING_MENTIONS` (default for co-occurrence pairs)

---

## Determinism

- `correlation_id = _k_stable_hash({"entities": sorted(entities), "signal": signal.value, "window": window_days})`
- Output sorted by strength (descending)
- Time window anchored to `evaluation_context.evaluation_timestamp` — no wall-clock

---

## Validation Results

| Test | Result |
|---|---|
| Empty input returns [] | PASS |
| Strength bounds [0, 1] | PASS |
| Sorted by strength desc | PASS |
| Has explanation string | PASS |
| Old evaluation_timestamp filters all items | PASS |
| Versions on all correlations | PASS |
| Co-occurrence returns list | PASS |
