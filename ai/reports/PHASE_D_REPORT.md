# PHASE D REPORT — Global Scraping Audit

> Executed: 2026-05-16
> Scope: data-core platform + poupi-baby integration
> Phases completed: Fase 1–7 + context files + Fase 9

---

## Summary

Phase D performed a full audit of every scraper, collector, scheduler job, and worker
in the Poupi platform. It classified all data sources by operational status, fixed four
active bugs (mock data pollution, missing schedulable flag, stale import, prometheus
misconfiguration), standardized log fields across all job entrypoints, and produced
the canonical scraping inventory matrix.

---

## Fase 1–2: Inventory and Classification

### New Field: `CollectorMetadata.schedulable`

**File:** `collectors/base.py`

Added `schedulable: bool = True` to the frozen dataclass. Default is `True` to preserve
backward compatibility. Collectors that return hardcoded demo data set it to `False`.

```python
# schedulable=False → collector existe para documentação/testes mas NÃO deve ser
# agendado automaticamente (ex: mocks de demo, placeholders sem fonte real).
# O scheduler verifica este flag antes de criar o job automático.
schedulable: bool = True
```

### Collectors Classified

| Collector | File | Status | schedulable | Fix Applied |
|---|---|---|---|---|
| `crypto.crypto_coin_ohlcv` | `collectors/crypto/crypto_coin_ohlcv.py` | `ACTIVE_REAL_DATA` | `True` (default) | None needed |
| `crypto.generic_price` | `collectors/crypto/generic_price.py` | `MOCK_ONLY` | `False` | Added flag |
| `ecommerce.generic_product` | `collectors/ecommerce/generic_product.py` | `MOCK_ONLY` | `False` | Added flag + updated description |
| `real_estate.generic_listing` | `collectors/real_estate/generic_listing.py` | `MOCK_ONLY` | `False` | Added flag |
| `sports_betting.generic_odds` | `collectors/sports_betting/generic_odds.py` | `MOCK_ONLY` | `False` | Added flag |
| `ecommerce.url_scraper` | `collectors/ecommerce/url_scraper.py` | `ACTIVE_REAL_DATA` | N/A (not in registry) | None |
| `ApolarCollector` | `app/modules/real_estate/collectors/apolar_collector.py` | `ACTIVE_PLAYWRIGHT` | N/A (domain job) | None |

**Bug found (Fase 1):** `ecommerce.generic_product` was missing `schedulable=False` — it was
being scheduled every 60 minutes, calling `https://example.com/products/demo-product-1` and
polluting the ecommerce pipeline with demo records.

---

## Fase 3–4: Disable Mocks + Scheduler Fixes

**File:** `scheduler/service.py` (complete rewrite of collector loop)

### Fix 1: Scheduler loop now filters mock collectors

```python
for collector_type in registry.all():
    metadata = collector_type.metadata
    if not metadata.schedulable:
        # Collector marcado como schedulable=False — dado mock/demo, não agendar.
        skipped.append(metadata.name)
        continue
    scheduler.add_job(collect_raw_job, ...)
```

**Before:** All 5 registered collectors were scheduled. 4 of them were calling
`https://example.com` every 5–120 minutes.

**After:** Only `crypto.crypto_coin_ohlcv` (the only `schedulable=True` collector)
gets a job. Skipped list logged at startup as info.

### Fix 2: `sports_odds:recurring` job disabled

The `sports_odds:recurring` job was calling `NbaOddsCollector` which used
`base_url="https://example.com"` — no real data source ever configured.

**Action:** Job commented out with restoration guide:
```python
# Sports odds: DESATIVADO — NbaOddsCollector usa base_url="https://example.com"
# Para reativar:
#   1. Implementar um collector concreto com URL real (ex: TheOddsAPI, BetAPI)
#   2. Restaurar o import de run_sports_odds_recurring_collection
#   3. Descomentar o bloco abaixo
```

### Fix 3: Removed stale import

`run_poupi_legacy_targets_job` was still imported in `service.py` after being replaced
by `run_ecommerce_url_targets_job` in Phase B. Import removed; comment added.

---

## Fase 5: Log Standardization

**Files:** `scheduler/jobs.py`, `app/modules/real_estate/scheduler.py`

Added `_log_job_run()` helper to `jobs.py`:

```python
def _log_job_run(
    *, job_name, run_id, domain, source, started_at,
    collected_count=0, persisted_count=0, normalized_count=0,
    failed_count=0, retry_count=0, error=None,
) -> None:
    duration_ms = int((time.monotonic() - started_at) * 1000)
    status = "error" if error else ("partial" if failed_count > 0 else "success")
    extra = {
        "run_id": run_id, "job": job_name, "domain": domain, "source": source,
        "status": status, "duration_ms": duration_ms, ...
    }
    if error:
        extra["last_failure_at"] = now_iso
        logger.error("Job run finished", extra=extra)
    else:
        extra["last_success_at"] = now_iso
        logger.info("Job run finished", extra=extra)
```

### Jobs Updated

| Job Function | File | Fields Added |
|---|---|---|
| `collect_raw_job` | `scheduler/jobs.py` | All 11 standard fields; domain derived from collector name prefix |
| `run_ecommerce_url_targets_job` | `scheduler/jobs.py` | All 11 standard fields; collected=targets, persisted=raw_saved_count, failed=error_count |
| `run_real_estate_daily_collection` | `app/modules/real_estate/scheduler.py` | All 11 standard fields; mapped from RealEstateCollectorResult (discovered_urls, collected_listings, errors) |

All jobs also emit a `"Job run started"` log at entry with `run_id`, `job`, `domain`, `source`
for full traceability (start→end correlation by `run_id`).

---

## Fase 6: prometheus.yml Update

**File:** `prometheus.yml` (data-core root)

| Change | Before | After |
|---|---|---|
| `poupi-jobs-api` job | Present (target: poupi-jobs-api:8001) | **Removed** — project doesn't exist |
| `poupi-baby-worker` job | Absent | **Added** (target: poupi-baby-worker:3002) |

```yaml
# Removed:
- job_name: poupi-jobs-api
  static_configs:
    - targets: ["poupi-jobs-api:8001"]

# Added:
- job_name: poupi-baby-worker
  static_configs:
    - targets: ["poupi-baby-worker:3002"]
  metrics_path: /metrics
```

---

## Fase 7: SCRAPING_MATRIX.md + scraping_status.md

| File | Location | Description |
|---|---|---|
| `docs/SCRAPING_MATRIX.md` | data-core | Full inventory: collectors, scrapers, jobs, workers, integrations, observability, gaps |
| `ai/contexts/scraping_status.md` | data-core | Compact AI context file for current scraping state |

---

## Context Files Created

| File | Project | Description |
|---|---|---|
| `ai/base/observability_standards.md` | poupi-baby | Log field standard, Prometheus metrics catalog, health check spec, Grafana dashboard guide |
| `ai/contexts/infrastructure.md` | poupi-baby | Docker services, networks, prometheus targets, worker metrics server, env vars, data flow diagram |
| `ai/contexts/scraping_status.md` | data-core | Active sources, mock list, scheduled jobs, downstream consumers, known gaps |

---

## Bug Inventory

| # | Bug | Root Cause | Fix | File |
|---|---|---|---|---|
| B-01 | Mock collectors scheduled every 5–120min; demo data polluting pipeline | `schedulable` flag missing; scheduler looped all registry entries | Added `schedulable=False` to 4 collectors; scheduler loop filters flag | `collectors/*/generic_*.py`, `base.py`, `scheduler/service.py` |
| B-02 | `ecommerce.generic_product` missing `schedulable=False` | Oversight in initial implementation | Added flag + updated description | `collectors/ecommerce/generic_product.py` |
| B-03 | `sports_odds:recurring` job hitting `https://example.com` every 30min | NbaOddsCollector never configured with real URL | Commented out job; left restoration guide | `scheduler/service.py` |
| B-04 | Stale `run_poupi_legacy_targets_job` import after Phase B | Import not cleaned up | Removed import; added comment | `scheduler/service.py` |
| B-05 | `prometheus.yml` scraping non-existent `poupi-jobs-api:8001` | Stale config; project never deployed | Removed job | `prometheus.yml` |
| B-06 | Worker metrics not scraped by Prometheus | `poupi-baby-worker` target never added | Added target `:3002` | `prometheus.yml` |
| B-07 | No structured log fields in scheduled jobs | No standard defined | Added `_log_job_run()` helper + wired to all job entrypoints | `scheduler/jobs.py`, `app/modules/real_estate/scheduler.py` |

---

## Validation Evidence

### Collector Classification

```
collectors/base.py → CollectorMetadata.schedulable: bool = True (line 24)

collectors/crypto/generic_price.py      → schedulable=False  # MOCK_ONLY
collectors/ecommerce/generic_product.py → schedulable=False  # MOCK_ONLY
collectors/real_estate/generic_listing.py → schedulable=False # MOCK_ONLY
collectors/sports_betting/generic_odds.py → schedulable=False # MOCK_ONLY

collectors/crypto/crypto_coin_ohlcv.py → schedulable not set = True (default, ACTIVE)
```

### Scheduler Loop Filter

```
scheduler/service.py lines 29-51:
  for collector_type in registry.all():
      if not metadata.schedulable:
          skipped.append(metadata.name)
          continue
      scheduler.add_job(collect_raw_job, ...)
  → Only crypto.crypto_coin_ohlcv creates a job (1 of 5 collectors)
```

### Log Fields at Job Start and End

```
collect_raw_job("crypto.crypto_coin_ohlcv"):
  START → {"run_id": "<uuid>", "job": "collect_raw_job", "domain": "crypto", "source": "crypto.crypto_coin_ohlcv"}
  END   → {"run_id": "<uuid>", "status": "success", "duration_ms": 1240, "last_success_at": "..."}

run_ecommerce_url_targets_job():
  START → {"run_id": "<uuid>", "job": "run_ecommerce_url_targets_job", "domain": "ecommerce", ...}
  END   → {"run_id": "<uuid>", "status": "success"/"partial"/"error", "collected_count": 17,
           "persisted_count": 17, "failed_count": 0, "duration_ms": 4230, ...}
```

---

## Remaining Gaps (Not Fixed in Phase D)

| Gap | File | Reason Not Fixed |
|---|---|---|
| G-02: `poupi_legacy_raw_collector` referenced in `run_collection_target_by_id` | `scheduler/jobs.py` | Backward compat; safe dead code (target would return "not supported" error) |
| G-03: `productUrl` = base URL in price-feed | `app/modules/ecommerce/` | Requires product slug extraction — separate feature scope |
| G-04: `imageUrl` absent in sync-created Offers | `backend/src/data-core/` | Requires data-core to expose image URLs in price-feed |
| G-05: Push notifications not implemented | `backend/src/notifications/` | Separate feature: Firebase FCM / APNs integration |
| G-07: poupi-crypto ↔ data-core end-to-end not validated | — | Requires live environment test |

---

## Files Changed (Complete List)

| File | Change Type | Description |
|---|---|---|
| `collectors/base.py` | Modified | Added `schedulable: bool = True` to CollectorMetadata |
| `collectors/crypto/generic_price.py` | Modified | `schedulable=False` |
| `collectors/ecommerce/generic_product.py` | Modified | `schedulable=False` + updated description |
| `collectors/real_estate/generic_listing.py` | Modified | `schedulable=False` |
| `collectors/sports_betting/generic_odds.py` | Modified | `schedulable=False` |
| `scheduler/service.py` | Rewritten | Scheduler loop filters mock collectors; sports_odds:recurring disabled; stale import removed |
| `scheduler/jobs.py` | Modified | Added `_log_job_run()` helper + imports; updated `collect_raw_job` and `run_ecommerce_url_targets_job` |
| `app/modules/real_estate/scheduler.py` | Rewritten | Full structured logging with standard fields; RealEstateCollectorResult mapping |
| `prometheus.yml` | Modified | Removed `poupi-jobs-api`; added `poupi-baby-worker` |
| `docs/SCRAPING_MATRIX.md` | Created | Full scraping inventory matrix |
| `ai/contexts/scraping_status.md` | Created | AI context for scraping state |
| `poupi-baby/ai/base/observability_standards.md` | Created | Log field standard + Prometheus metrics catalog |
| `poupi-baby/ai/contexts/infrastructure.md` | Created | Docker/network/env/data flow reference |

---

*Phase D complete — Global Scraping Audit*
