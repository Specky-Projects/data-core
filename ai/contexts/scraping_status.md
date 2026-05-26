# Scraping Status — data-core

> Last updated: 2026-05-16 (Phase D Global Scraping Audit)
> Full detail: `docs/SCRAPING_MATRIX.md`

## Active Data Sources (Production)

| Domain | Source | Collector | Frequency | Notes |
|---|---|---|---|---|
| **ecommerce** | drogasil, drogaraia, paguemenos | `ecommerce.url_scraper` (VTEX) | 2h | 17 targets; VTEX Catalog API + JSON-LD fallback |
| **real_estate** | apolar.com.br | `ApolarCollector` (Playwright) | Daily 03:30 | Curitiba; max 25 listings/run |
| **crypto** | Binance (CCXT) | `CryptoCoinOHLCVCollector` | 15 min | BTC/ETH/SOL/BNB/ADA × 15m,1h |

## Mock/Disabled Collectors

| Collector | Status | Reason |
|---|---|---|
| `crypto.generic_price` | MOCK_ONLY | Hardcoded BTC-BRL demo data |
| `ecommerce.generic_product` | MOCK_ONLY | Hardcoded demo product |
| `real_estate.generic_listing` | MOCK_ONLY | Hardcoded demo listing |
| `sports_betting.generic_odds` | MOCK_ONLY | Hardcoded odds demo |
| `sports_odds:recurring` job | DISABLED | NbaOddsCollector had no real URL; job commented out |

All mock collectors have `schedulable=False` in `CollectorMetadata` — scheduler loop skips them automatically.

## Key Scheduler Jobs

```
collector:crypto.crypto_coin_ohlcv    → every 15min (ACTIVE)
ecommerce:url_scraper_targets          → every 2h    (ACTIVE)
real_estate:daily                      → daily 03:30  (ACTIVE, Playwright)
pipeline:normalize                     → every 15min  (ACTIVE if enabled)
pipeline:analytics                     → every 60min  (ACTIVE if enabled)
maintenance:cleanup_stale_runs         → every 15min  (ACTIVE)
maintenance:alert_webhook              → every 1h     (ACTIVE if webhook URL set)
maintenance:data_retention             → Sunday 02:00 (ACTIVE)
sports_odds:recurring                  → DISABLED
```

## Downstream Consumers

- **poupi-baby**: pulls `GET /api/v1/poupi-baby/price-feed` every 2h for diaper price alerts
- **poupi-crypto**: pushes OHLCV via `POST /api/v1/crypto/push_ohlcv_batch`; pulls signals via candles-feed

## Observability

- All scheduled jobs emit structured log with: `run_id`, `job`, `domain`, `source`,
  `status`, `duration_ms`, `collected_count`, `persisted_count`, `failed_count` (Phase D Fase 5)
- Prometheus scraping configured in `prometheus.yml` for: data-core API, poupi-baby backend+worker, poupi-crypto

## Known Gaps

- **G-01**: Sports odds job disabled — no real bookmaker API integrated yet
- **G-02**: `poupi_legacy_raw_collector` still referenced in `run_collection_target_by_id` (dead code)
- **G-07**: poupi-crypto ↔ data-core end-to-end not validated in production
