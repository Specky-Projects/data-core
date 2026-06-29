# BUSINESS OS 1.5 — CHANGE INVENTORY

**Date:** 2026-06-29  
**Version:** business-os-1.5-opportunity

---

## New Files

| File | Description |
|---|---|
| `app/opportunity/__init__.py` | Module root |
| `app/opportunity/dto.py` | Canonical Opportunity Model — 9 version constants, 9 DTOs |
| `app/opportunity/discovery.py` | 2 discovery methods (entity presence + correlation) |
| `app/opportunity/scoring.py` | 10-dimension evidence-derived scoring |
| `app/opportunity/ranking.py` | 6-strategy deterministic ranking |
| `app/opportunity/lifecycle.py` | 6-stage lifecycle tracker + snapshot recording |
| `app/opportunity/evolution.py` | Evolution direction + explanation builder |
| `app/opportunity/portfolio.py` | Hierarchical portfolio (domain → type) |
| `app/opportunity/health.py` | 10-dimension Opportunity Health |
| `app/opportunity/learning.py` | Adaptive Intelligence bridge (no new engine) |
| `app/opportunity/orchestrator.py` | Full pipeline orchestrator |
| `app/opportunity/api.py` | FastAPI routes: /opportunity/version, /health, /report |
| `app/opportunity/tests/__init__.py` | Tests sub-package |
| `app/opportunity/tests/test_opportunity_stage_1_5.py` | 105 scientific tests |

## Modified Files

None — no existing files modified.

## Deliverable Documents

| Document | Purpose |
|---|---|
| `BUSINESS_OS_1_5_OPPORTUNITY_MODEL.md` | Canonical model documentation |
| `BUSINESS_OS_1_5_DISCOVERY_REPORT.md` | Discovery algorithm documentation |
| `BUSINESS_OS_1_5_SCORING_REPORT.md` | Scoring documentation |
| `BUSINESS_OS_1_5_RANKING_REPORT.md` | Ranking documentation |
| `BUSINESS_OS_1_5_LIFECYCLE_REPORT.md` | Lifecycle documentation |
| `BUSINESS_OS_1_5_HEALTH_REPORT.md` | Health documentation |
| `BUSINESS_OS_1_5_CERTIFICATION.md` | Full certification + red team audit |
| `BUSINESS_OS_1_5_EXECUTIVE_REPORT.md` | Executive summary |
| `BUSINESS_OS_1_5_CHANGE_INVENTORY.md` | This file |
| `BUSINESS_OS_1_5_EVIDENCE.json` | Machine-readable evidence |

## Test Count

| Before 1.5 | After 1.5 | New |
|---|---|---|
| 1282 passed | 1387 passed | +105 |

## Backward Compatibility

- All 1.3 + 1.4 imports: unchanged
- `app/adaptive_intelligence/`: untouched
- `app/knowledge/`: untouched
- No migrations required (in-memory pipeline)
- 23 pre-existing failures unchanged (auto-healing, performance-guard)
