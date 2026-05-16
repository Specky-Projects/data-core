# data-core — AI Operational Context

> For AI agents. Dense, machine-optimized. Updated: 2026-05-16.
> Full human docs: `/docs/`. Source of truth: this file + `/docs/`.

---

## What this project is

Production ETL platform (Python 3.12 / FastAPI) collecting, normalizing and computing analytics
for 4 domains: **crypto**, **ecommerce**, **real_estate**, **sports_betting**.

**Only crypto is fully active** — the others run on demo/stub data.

**Runtime:** 3 Docker containers on Hetzner via Coolify. One shared PostgreSQL + Redis instance.

---

## Runtime topology

| Container | Role | Key env |
|---|---|---|
| `api` | FastAPI HTTP server + runs `alembic upgrade head` on start | `SCHEDULER_ENABLED=false` |
| `scheduler` | APScheduler — collects raw data, runs domain jobs | `SCHEDULER_COLLECTORS_ENABLED=true` |
| `worker` | APScheduler — normalize + analytics | `SCHEDULER_PIPELINE_ENABLED=true` |

- Coolify app UUID: `dvq6dwsagsw4p4oqwuw7bak9`
- Docker network: `dvq6dwsagsw4p4oqwuw7bak9` (internal), `coolify` (shared), `infra_internal`
- API alias on coolify network: `data-core-api` (used by poupi-crypto to reach this API)
- Current commit: check `docker ps` image tag

---

## Database

- **Host:** `multi_project_infra-postgres-1` (container name) / `postgres` (docker-compose alias)
- **DB:** `data_core_db`
- **User:** `data_core_user`
- **Key tables:**

| Table | Purpose |
|---|---|
| `raw_collections` | Stage 1: raw JSON from collectors. `processing_status = normalization_pending → normalized` |
| `normalized_market_candles` | Stage 2: OHLCV candles. UNIQUE `(source, symbol, timeframe, timestamp)` |
| `normalized_crypto_snapshots` | Stage 2: price snapshots |
| `normalized_products` | Stage 2: ecommerce products |
| `normalized_real_estate_listings` | Stage 2: property listings |
| `normalized_sports_odds` | Stage 2: betting odds |
| `trading_analytics` | Stage 3: crypto signals (RSI, MA, ATR, ADX, signal, confidence, regime) |
| `product_price_analytics` | Stage 3: price trends (7/30/90d avg, z-score) |
| `real_estate_analytics` | Stage 3: price/m2, opportunity score (partial stub) |
| `sports_odds_analytics` | Stage 3: line movement, CLV (partial stub) |
| `pipeline_runs` | Observability: every stage execution (domain, stage, status, duration, items) |
| `pipeline_failures` | Observability: per-failure details + traceback |
| `collection_targets` | Ecommerce scrape targets (seed to activate ecommerce) |
| `collector_errors` | Circuit breaker events + dead letters |
| `alembic_version` | Current migration: `0015_pipeline_observability` |

---

## ETL pipeline (per domain)

```
Collector (APScheduler, scheduler container)
  → raw_collections (checksum dedup)
    → Normalizer (APScheduler, worker container, every 15min)
      → normalized_* (domain table)
        → Analytics Processor (APScheduler, worker container, every 60min)
          → *_analytics (domain table)
          → pipeline_runs (PipelineRecorder)
          → Prometheus metrics
```

Reference: `/docs/DATA_FLOW.md`

---

## Key source files

| File | Role |
|---|---|
| `app/main.py` | FastAPI app factory, lifespan, middleware, `/health`, `/live`, `/ready` |
| `api/metrics.py` | All Prometheus metrics + `measure_pipeline_stage()` context manager |
| `app/middleware/correlation.py` | `CorrelationMiddleware` — injects `X-Correlation-ID` + `X-Trace-ID` |
| `app/pipeline/recorder.py` | `PipelineRecorder` — context manager for every stage run |
| `app/pipeline/models.py` | `PipelineRun` + `PipelineFailure` SQLAlchemy models |
| `logs/config.py` | `CorrelationFilter`, `PipelineFilter`, `set_pipeline_context()` |
| `scheduler/jobs.py` | `normalize_job()` + `analytics_job()` — both wrapped with `PipelineRecorder` |
| `scheduler/circuit_breaker.py` | Opens after 5 consecutive failures; manual reset via `reopen_source_circuit()` |
| `scheduler/retry.py` | `with_retry(fn, max_retries=3, backoff_seconds=5)` + dead-letter write |
| `alembic/versions/0015_pipeline_observability.py` | Last migration: `pipeline_runs` + `pipeline_failures` |
| `collectors/registry.py` | All collectors registered here |

---

## API endpoints

Base URL (internal): `http://data-core-api:8000`  
Auth: `X-API-Key` header when `API_KEY_ENABLED=true`

| Endpoint | Purpose |
|---|---|
| `GET /live` | Liveness probe (always 200, no DB) |
| `GET /ready` | Readiness probe (postgres + redis + scheduler) |
| `GET /health` | Full dependency check |
| `GET /metrics` | Prometheus scrape |
| `GET /api/v1/crypto/analytics` | Trading analytics rows |
| `GET /api/v1/analytics/signals` | Signals feed (used by poupi-crypto) |
| `GET /api/v1/crypto/feed` | OHLCV candles feed |
| `POST /api/v1/operations/pipeline/run` | Manual pipeline trigger |
| `GET /api/v1/operations/alerts` | Operational health (dead letters, circuit breakers) |

Full reference: `/docs/API_ENDPOINTS.md`

---

## Observability

### Prometheus metrics (defined in `api/metrics.py`)
- `pipeline_stage_runs_total{domain, stage, status}` — Counter
- `pipeline_stage_duration_seconds{domain, stage}` — Histogram
- `pipeline_stage_last_success_timestamp_seconds{domain, stage}` — Gauge
- `collection_raw_saved_total{domain, collector_name}` — Counter ⚠️ NOT YET WIRED in collector_worker.py
- `circuit_breaker_opens_total{module, source_name}` — Counter
- `job_dead_letters_total{job_name}` — Counter

> ⚠️ Known gap: pipeline stage metrics are updated in worker/scheduler process,
> not in the API process. `/metrics` on API shows metric definitions but no data.
> Pipeline runs are tracked via `pipeline_runs` DB table (fully operational).

### Health probes
- `/live` — liveness: process alive, no DB
- `/ready` — readiness: postgres + redis + scheduler check
- `/health` — full: postgres + redis status + env

### Structured logging
- `LOG_JSON=false` (default in production) — plain text with correlation IDs
- `LOG_JSON=true` — JSON with `correlation_id`, `trace_id`, `pipeline_domain`, `pipeline_stage`
- Set pipeline context: `set_pipeline_context(domain="crypto", stage="collection")`

### Grafana dashboards
| UID | Name | Source |
|---|---|---|
| `data-core-ops-v1` | Operational — pipeline runs, failures, stage durations | Prometheus + PostgreSQL |
| `data-core-perf-v1` | Performance — collection volume, circuit breakers | Prometheus |

Full reference: `/docs/OBSERVABILITY.md`

---

## Jobs and schedules

Reference: `/docs/JOBS_AND_SCHEDULES.md`

**Key intervals:**
- Crypto collection: every 15 min (5 pairs × 2 TF via Binance/CCXT)
- Normalization: every 15 min (worker)
- Analytics: every 60 min (worker)
- Data retention: Sunday 02:00 (cleans raw/normalized/analytics by retention policy)

---

## Deployment

Coolify deploys from GitHub `main` branch → `https://github.com/poupi-hub/data-core.git`

**To deploy:**
1. Push to `main`
2. Trigger Coolify build (via DB queue dispatch — see `docs/AUDIT.md` §6 or RUNBOOK.md)
3. API container runs `alembic upgrade head` on start

**Current production state (as of 2026-05-16):**
- Image tag: `503fddf...`
- Migration: `0015_pipeline_observability` (head)
- All 3 containers: healthy
- `data-core-api` alias: active on `coolify` network

---

## Known gaps (from audit)

| Priority | Gap | Fix |
|---|---|---|
| P1 | `collection_raw_saved_total` not incremented in `collector_worker.py` | Import metric, call `.inc()` after save |
| P1 | Ecommerce collectors not active | Seed `collection_targets` with real URLs |
| P1 | Sports odds API key missing | Set `THE_ODDS_API_KEY` env var |
| P2 | `LOG_JSON=true` not set in production | Add to Coolify env vars |
| P2 | Redis cache disabled (`CACHE_ENABLED=false`) | Enable + add TTL to analytics routes |
| P2 | Pipeline staleness alerts missing | Add to `prometheus/rules/data-core-alerts.yml` |
| P2 | Hardcoded credentials in `docker-compose.yml` | Replace with `${VAR}` |
| P3 | Prometheus metrics multi-process gap | Push metrics from worker; or use Pushgateway |

Full audit: `/docs/AUDIT.md`

---

## Documentation map

| File | Audience | Content |
|---|---|---|
| `ai/CONTEXT.md` | AI agents | This file — operational context |
| `ai/RUNBOOK.md` | AI agents | Diagnose + fix + deploy playbook |
| `ai/DOC_SYNC_RULES.md` | AI agents | Documentation sync rules (mandatory) |
| `docs/DATA_FLOW.md` | Human + AI | ETL flow per domain |
| `docs/JOBS_AND_SCHEDULES.md` | Human + AI | All jobs, triggers, reliability |
| `docs/API_ENDPOINTS.md` | Human + AI | All REST endpoints with examples |
| `docs/OBSERVABILITY.md` | Human + AI | Metrics, alerts, logs, health checks |
| `docs/AUDIT.md` | Human + AI | Audit report, gaps, priority matrix |
| `README.md` | Human | Project overview, quick start |
| `AGENTS.md` | AI agents | Coding rules, architecture constraints |
