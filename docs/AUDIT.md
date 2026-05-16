# data-core — Technical Audit Report

> Audited: 2026-05-16. Auditor: AI architecture review (Claude).  
> Scope: full codebase, production deployment on Hetzner/Coolify.

---

## Executive Summary

data-core is a **production-grade, multi-domain ETL platform** in Python 3.12/FastAPI.
The crypto pipeline is fully operational with zero errors. Other domains (ecommerce,
real_estate, sports_betting) have functional code but are running on demo/stub data only.

**Overall grade:** B+ (strong architecture, gaps in domain activation and observability depth)

---

## 1. What is working correctly ✅

| Area | Evidence |
|---|---|
| Crypto collection (5 pairs × 2 TF) | 2122 raw records, collected every 5 min, zero errors |
| Normalization pipeline | normalized_market_candles with UNIQUE constraint enforced |
| Analytics computation | trading_analytics: RSI, MA, ATR, ADX, signal, confidence, regime |
| Deduplication | `(source, symbol, timeframe, timestamp)` UNIQUE on candles |
| Circuit breaker | Implemented, Prometheus metric emitted on open |
| Retry + dead letter | Exponential backoff, dead-letter DB records + metrics |
| Data retention | Sunday 2am job cleans raw/normalized/analytics by retention policy |
| Prometheus metrics | /metrics endpoint, fastapi-instrumentator auto-instrumentation |
| Alert rules | 7 rules in prometheus/rules/data-core-alerts.yml |
| Data lineage | raw_collection_id → normalized_id → analytics_id tracked |
| API auth | X-API-Key header (optional, configurable) |
| Rate limiting | slowapi with per-key or per-IP rate limiting |

---

## 2. Gaps identified ⚠️

### 2A. Domain activation — Critical gap
**Problem:** Only `crypto` domain is actively collecting. All other domains have only 1 demo record.

| Domain | Status | Root cause |
|---|---|---|
| ecommerce | Demo only | PoupiLegacyRawCollector scrapes Drogasil only when `collection_targets` contains entries. Currently only 1 seeded target. No production scraper running. |
| real_estate | Demo only | `GenericRealEstateCollector` is a demo returning a hardcoded listing. Apolar/VivaReal scrapers exist but are not registered in scheduler. |
| sports_betting | Demo only | `GenericOddsCollector` returns a demo. NbaOddsCollector exists but requires API key config. |

**Impact:** 75% of the platform's intended data is not flowing.

**Fix per domain:**
```
ecommerce:   Seed collection_targets with real product URLs. Activate PoupiLegacyRawCollector.
             Set scraping frequency (e.g., 60 min per product group).
real_estate: Configure ApolarCollector with real city/URL params. Register in scheduler.
sports_odds: Configure THE_ODDS_API_KEY. Activate NbaOddsCollector.
```

---

### 2B. Analytics processors — Stubs
**Problem:** Some analytics processors return placeholder values (None or 0).

| Processor | Real computation | Stubs |
|---|---|---|
| CryptoAnalyticsProcessor | RSI, MA, ATR, ADX, signal, confidence ✅ | None |
| ProductPriceAnalyticsProcessor | 7/30/90d avg, z-score ✅ | CLV |
| RealEstateAnalyticsProcessor | price_per_m2 ✅ | neighborhood_avg, opportunity_score |
| SportsOddsAnalyticsProcessor | opening_odd, line_movement ✅ | closing_odd, CLV, EV |

**Impact:** Downstream consumers (poupi-baby, poupi-frontend dashboards) will receive incomplete analytics.

---

### 2C. Pipeline observability — Partially filled (ADDED 2026-05-16)
**Before this audit:** No per-stage timing, no `pipeline_runs` table, no structured log context.  
**After this audit:** `pipeline_runs`, `pipeline_failures`, `PipelineRecorder`, enhanced metrics, correlation middleware added.

**Remaining gap:** `collection_raw_saved_total`, `collection_duration_seconds` are defined in metrics.py but NOT yet incremented from `workers/collector_worker.py`. The collector worker needs to import and update these metrics.

**Fix:** In `workers/collector_worker.py`, after saving raw records:
```python
from api.metrics import collection_raw_saved_total, collection_duration_seconds
collection_raw_saved_total.labels(domain=domain, collector_name=collector_name).inc(saved_count)
```

---

### 2D. No `/ready` or `/live` endpoints — FIXED 2026-05-16
Both endpoints now implemented in `app/main.py`. Docker healthcheck currently uses `/health` — should be updated to use `/ready` in production.

**Recommended Dockerfile change:**
```dockerfile
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD wget -qO- http://localhost:8000/ready || exit 1
```

---

### 2E. Logging structure — IMPROVED 2026-05-16
Before: plain text only, no correlation IDs.  
After: `CorrelationFilter` + `PipelineFilter` inject IDs; JSON format available via `LOG_JSON=true`.

**Remaining gap:** Scheduler/worker containers should set `LOG_JSON=true` in production for Loki/Grafana log ingestion. Currently logs are unstructured in production containers.

---

### 2F. Redis usage — underutilised
**Problem:** Redis is running but `cache_enabled=false` in all production containers.  
**Impact:** No caching of expensive queries (e.g., analytics feeds that recalculate on every request).

**Recommendation:**
```python
# In api routes that serve analytics feeds, add Redis cache with 5-min TTL:
cache_key = f"analytics:{symbol}:{timeframe}:{limit}"
cached = redis.get(cache_key)
if cached:
    return json.loads(cached)
# ... compute ...
redis.setex(cache_key, 300, json.dumps(result))
```

---

### 2G. No autoscaling or backpressure
**Problem:** `normalize_job` and `analytics_job` run with fixed `limit=100` per cycle.
If raw_collections accumulates (e.g., backfill of 2000+ records), processing takes many cycles.

**Evidence:** After backfill, analytics table showed ~200 records processed across multiple cycles rather than all at once.

**Recommendation:** Add a `MAX_BACKLOG_LIMIT` env var and increase limit dynamically when queue depth exceeds a threshold.

---

### 2H. Single-process pipeline — risk of blocking
**Problem:** `normalize_job` and `analytics_job` run synchronously in APScheduler threads.
A slow analytics computation will block subsequent cycles.

**Current mitigation:** `max_instances=1` and `coalesce=true` prevent parallel execution.  
**Long-term recommendation:** Migrate heavy jobs to Celery workers with Redis as broker.

---

### 2I. Disk and build cache pressure
**Current state:** Docker disk usage:
- Images: 22GB (2.15GB reclaimable)
- Build cache: 5.1GB (4.9GB reclaimable)
- Total disk: 68% used (12GB free)

**Action required:** Run `docker buildx prune --filter until=24h` to reclaim 4.9GB.  
**Monitor:** Set alert if disk exceeds 85%.

---

### 2J. Security — hardcoded credentials
**Problem (audit-report.md):** Passwords hardcoded in some docker-compose files.  
**Status:** data-core production deployment via Coolify uses encrypted env vars ✅  
**Status:** Local docker-compose.yml in the repo still has hardcoded credentials ⚠️

**Fix:** Replace all hardcoded values with `${VARIABLE}` and document in `.env.example`.

---

## 3. Bottlenecks and scaling risks

| Bottleneck | Current impact | Threshold risk | Recommendation |
|---|---|---|---|
| Single PostgreSQL instance | Low (shared among 4 services) | High read load from multiple consumers | Add pgBouncer connection pooler; consider read replica |
| `normalized_market_candles` growth | ~200 rows/pair/TF now; growing 4/hr | 10M+ rows in 1 year | Partition by `timestamp` month; enforce retention |
| `trading_analytics` growth | Mirrors candles 1:1 | Same as above | Same partitioning |
| `raw_collections` growth | 2122 rows now; all crypto | Unbounded if retention job fails | Verify retention job Sunday execution; monitor table size |
| Synchronous job blocking | 1 thread per job | If analytics takes >15min, normalization starves | Migrate to Celery |
| 5 collectors × 2 TF × 15min | Currently fine | At 20+ pairs, 300 items/cycle, may miss window | Increase limit or parallelize |

---

## 4. Inconsistencies found

| Area | Inconsistency |
|---|---|
| `collection_targets` | Seeded with 1 Drogasil target but `ensure_default_collection_targets()` is idempotent — table has 0 additional entries populated |
| `sports_odds_analytics` | `SportsOddsAnalyticsProcessor` references `closing_odd` field but that field has no source of truth in current pipeline |
| Schema docs | `docs/database/schemas.md` references `poupi_data` database but actual production DB is `data_core_db` |
| Alembic | `39d33505c86b_pipeline_layers.py` migration exists alongside numbered migrations — unclear if applied |
| Port references | Some docs reference `:5432`, `:5433`, `:5434`, `:5436` — actual production uses `:5432` via container name |

---

## 5. Priority matrix

| Priority | Item | Effort | Impact |
|---|---|---|---|
| 🔴 P1 | Activate ecommerce collectors (real URLs in collection_targets) | Low | High |
| 🔴 P1 | Configure sports odds API key (THE_ODDS_API_KEY) | Low | High |
| 🔴 P1 | Run `docker buildx prune` (free 4.9GB) | Trivial | Medium |
| 🟡 P2 | Increment `collection_raw_saved_total` metric in collector_worker | Low | Medium |
| 🟡 P2 | Enable `LOG_JSON=true` in production containers | Trivial | Medium |
| 🟡 P2 | Enable Redis cache for analytics feed endpoints (TTL 5min) | Medium | High |
| 🟡 P2 | Add prometheus alerting rules for pipeline staleness | Low | High |
| 🟡 P2 | Replace hardcoded docker-compose credentials with `${VAR}` | Low | Critical (security) |
| 🟢 P3 | Implement `neighborhood_avg_price_m2` in RealEstateAnalyticsProcessor | Medium | Medium |
| 🟢 P3 | Implement CLV and EV in SportsOddsAnalyticsProcessor | Medium | Medium |
| 🟢 P3 | Add table partitioning for normalized_market_candles + trading_analytics | High | High |
| 🟢 P3 | Migrate analytics_job to Celery | High | High |
| 🟢 P3 | Add pgBouncer | Medium | Medium |

---

## 6. What was implemented in this audit session (2026-05-16)

| Deliverable | File | Description |
|---|---|---|
| Enhanced Prometheus metrics | `api/metrics.py` | Pipeline stage, collection, DB pool metrics + `measure_pipeline_stage()` context manager |
| Correlation middleware | `app/middleware/correlation.py` | `X-Correlation-ID` + `X-Trace-ID` per request, stored in contextvars |
| Structured logging | `logs/config.py` | `CorrelationFilter` + `PipelineFilter` inject IDs; JSON format with field renaming |
| Pipeline models | `app/pipeline/models.py` | `PipelineRun` + `PipelineFailure` SQLAlchemy models |
| Alembic migration | `alembic/versions/0015_pipeline_observability.py` | Creates `pipeline_runs` and `pipeline_failures` tables |
| Pipeline recorder | `app/pipeline/recorder.py` | Context manager: inserts pipeline_run, updates on exit, records failures |
| Jobs integration | `scheduler/jobs.py` | `normalize_job` and `analytics_job` now wrapped with `PipelineRecorder` |
| /live endpoint | `app/main.py` | Liveness probe (process alive, no DB check) |
| /ready endpoint | `app/main.py` | Readiness probe (postgres + redis + scheduler) |
| CorrelationMiddleware | `app/main.py` | Added to FastAPI app |
| Operational Grafana dashboard | `docs/grafana-dashboard-data-core-ops.json` | pipeline_runs table, stage metrics, domain staleness, HTTP stats |
| DATA_FLOW.md | `docs/DATA_FLOW.md` | Full ETL flow per domain |
| JOBS_AND_SCHEDULES.md | `docs/JOBS_AND_SCHEDULES.md` | All scheduler jobs, triggers, reliability |
| API_ENDPOINTS.md | `docs/API_ENDPOINTS.md` | All REST endpoints with examples |
| OBSERVABILITY.md | `docs/OBSERVABILITY.md` | Metrics, alerts, logs, health checks, SQL queries |
| AUDIT.md | `docs/AUDIT.md` | This document |
