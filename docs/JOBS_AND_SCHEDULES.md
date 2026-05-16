# data-core — Jobs and Schedules

> AI-friendly reference. Auto-contained. Updated: 2026-05-16.

## Runtime topology

Three Docker containers share the same image but run different roles:

| Container | `SCHEDULER_ENABLED` | `SCHEDULER_COLLECTORS_ENABLED` | `SCHEDULER_PIPELINE_ENABLED` | Role |
|---|---|---|---|---|
| `api` | false | — | — | Serves HTTP only; no background jobs |
| `scheduler` | true | true | false | Runs collectors; triggers normalization |
| `worker` | true | false | true | Runs normalize + analytics jobs |

APScheduler timezone: `America/Sao_Paulo`  
Max instances per job: 1 (coalesce=true)

---

## Job registry

### Collection jobs (scheduler container)

| Job function | Trigger | Interval | What it does |
|---|---|---|---|
| `collect_raw_job("crypto.crypto_coin_ohlcv")` | IntervalTrigger | 15 min | Fetches OHLCV for 5 pairs × 2 timeframes from Binance |
| `collect_raw_job("crypto.generic_price")` | IntervalTrigger | 60 min | Generic price snapshot |
| `collect_raw_job("ecommerce.generic_product")` | IntervalTrigger | 60 min | Demo ecommerce product |
| `collect_raw_job("real_estate.generic_listing")` | IntervalTrigger | 120 min | Demo listing |
| `collect_raw_job("sports_betting.generic_odds")` | IntervalTrigger | 15 min | Demo odds |
| `run_poupi_legacy_targets_job()` | IntervalTrigger | 8 h | Scrapes `collection_targets` via PoupiLegacyRawCollector |
| `run_real_estate_daily_collection()` | CronTrigger | Daily 03:30 | Batch real estate scrape |
| `run_sports_odds_recurring_collection()` | IntervalTrigger | 30 min | Sports odds recurring |

### Pipeline jobs (worker container)

| Job function | Trigger | Interval | What it does |
|---|---|---|---|
| `normalize_job()` | IntervalTrigger | 15 min | Normalizes all pending raw records (all domains) |
| `analytics_job()` | IntervalTrigger | 60 min | Computes analytics for all pending normalized records |

### Maintenance jobs (scheduler container)

| Job function | Trigger | What it does |
|---|---|---|
| `cleanup_stale_runs_job(ttl_minutes=30)` | Every 15 min | Marks runs stuck > 30 min as failed; triggers circuit breaker |
| `alert_webhook_job()` | Every 1 h | Sends operational alerts to webhook URL if anomalies detected |
| `data_retention_job()` | CronTrigger Sunday 02:00 | Deletes old records per retention policy |

---

## Job internals

### collect_raw_job(collector_name)
```
1. Calls run_collector_job(collector_name)
2. Creates asyncio event loop
3. Opens DB session
4. Calls run_collector_by_name(collector_name, db)
   → CollectorWorker.run()
   → BaseCollector.collect() → list[CollectedItem]
   → Saves each item to raw_collections (checksum dedup)
   → Writes CollectionRun record (status=success|failed)
5. Closes session
```

Prometheus metrics updated: `collection_raw_saved_total`, `collection_raw_duplicates_total`,  
`collection_errors_total`, `collection_duration_seconds`

### normalize_job(module=None, limit=100)
```
1. Loads normalizer registry (register_pipeline_modules)
2. For each module × normalizer:
   a. Opens PipelineRecorder(domain, stage="normalization")  ← NEW
   b. Opens DB session
   c. Calls normalizer.run(limit=limit)
      → Queries raw_collections WHERE processing_status='normalization_pending'
      → For each record: validates → inserts normalized row → marks 'normalized'
   d. PipelineRecorder records timing, status, item counts to pipeline_runs
   e. Prometheus: pipeline_stage_duration_seconds, pipeline_stage_runs_total
```

### analytics_job(module=None, limit=100)
```
1. Loads analytics registry
2. For each module:
   a. Opens PipelineRecorder(domain, stage="analytics")  ← NEW
   b. Opens DB session
   c. Calls processor.run(limit=limit)
      → Queries normalized_* WHERE analytics_status='pending'
      → Computes indicators → inserts *_analytics row → marks 'processed'
   d. PipelineRecorder records timing, status, item counts
   e. Prometheus: pipeline_stage_duration_seconds, pipeline_stage_runs_total
```

---

## Reliability mechanisms

### Circuit breaker (`scheduler/circuit_breaker.py`)
- Checks last 5 collection runs for a (module, source_name) pair
- If all 5 are `failed` → opens circuit:
  - Deactivates `collection_targets` for that source
  - Writes `CollectorError(error_type="CircuitOpen")`
  - Increments `circuit_breaker_opens_total` metric
- Circuit does NOT auto-reset — requires manual call to `reopen_source_circuit()`

### Retry + Dead Letter (`scheduler/retry.py`)
- `with_retry(fn, max_retries=3, backoff_seconds=5)` wraps normalize + analytics
- Exponential backoff: `wait = backoff_seconds × attempt`
- After max_retries exceeded:
  - Writes `CollectorError(error_type="JobDeadLetter")` with full traceback
  - Increments `job_dead_letters_total` metric
  - Re-raises exception (scheduler logs it as failed)

### Stale run cleanup
- Runs stuck in `status=running` for > 30 min are forcibly marked `failed`
- Triggers circuit breaker check for affected sources

### Locking (target runner)
- Before collecting a target, checks for an existing `CollectionRun(status=running)` for same
  `(module, source_name, collector_name)` started within the last 30 min
- Skips the target if locked (prevents parallel scraping of same URL)

---

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `SCHEDULER_ENABLED` | true | Enable APScheduler |
| `SCHEDULER_COLLECTORS_ENABLED` | true | Register collector jobs |
| `SCHEDULER_PIPELINE_ENABLED` | true | Register normalize + analytics jobs |
| `SCHEDULER_DOMAIN_JOBS_ENABLED` | true | Register domain-specific jobs |
| `SCHEDULER_TIMEZONE` | America/Sao_Paulo | APScheduler timezone |
| `SYMBOLS` | BTC/USDT,ETH/USDT,SOL/USDT,BNB/USDT,ADA/USDT | Crypto pairs to collect |
| `TIMEFRAMES` | 15m,1h | Crypto timeframes |

---

## Monitoring dead letters and circuit breakers

```bash
# Dead letters (unresolved)
curl -s http://localhost:8000/api/v1/operations/alerts | jq '.dead_letters'

# Circuit breaker open sources
curl -s http://localhost:8000/api/v1/operations/alerts | jq '.circuit_breakers'

# Prometheus metrics
curl -s http://localhost:8000/metrics | grep -E 'job_dead_letters|circuit_breaker'

# Recent pipeline runs
psql -U data_core_user -d data_core_db -c \
  "SELECT domain, stage, status, duration_seconds, items_processed FROM pipeline_runs ORDER BY started_at DESC LIMIT 20;"
```
