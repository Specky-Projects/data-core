# data-core — API Endpoints

> AI-friendly reference. Auto-contained. Updated: 2026-05-16.
> Base URL (production): `http://data-core-api:8000`
> Auth: `X-API-Key: <DATA_CORE_API_KEY>` header (when `API_KEY_ENABLED=true`)

---

## Observability (no auth required)

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Full dependency check: postgres + redis. Returns `{"status":"ok"\|"degraded", "dependencies":{...}}` |
| GET | `/live` | Liveness probe. Always 200 if process is alive. No DB check. |
| GET | `/ready` | Readiness probe. Checks postgres, redis (if enabled), scheduler. Returns 503 if not ready. |
| GET | `/metrics` | Prometheus scrape endpoint (text/plain). |

### /health response
```json
{
  "status": "ok",
  "app": "data-core",
  "environment": "production",
  "dependencies": {
    "postgres": { "status": "ok" },
    "redis": { "status": "ok" }
  }
}
```

### /ready response (503 example)
```json
{
  "ready": false,
  "checks": {
    "postgres": "ok",
    "redis": "error: Connection refused",
    "scheduler": "ok"
  },
  "app": "data-core"
}
```

---

## Operations API — `/api/v1/operations`

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/operations/alerts` | Operational health: stale raw data, pending items, dead letters, circuit breakers |
| POST | `/api/v1/operations/pipeline/run` | Trigger normalize + analytics for all pending items (manual) |
| GET | `/api/v1/operations/pipeline/status` | Current pipeline status: pending counts per domain |

### POST /api/v1/operations/pipeline/run
```json
// Body (optional)
{ "module": "crypto", "limit": 100 }

// Response
{ "normalized": 10, "analytics": 10, "errors": 0 }
```

---

## Crypto module — `/api/v1/crypto`

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/crypto/candles` | OHLCV candles from normalized_market_candles |
| GET | `/api/v1/crypto/snapshots` | Price snapshots from normalized_crypto_snapshots |
| GET | `/api/v1/crypto/analytics` | Full analytics rows from trading_analytics |

### GET /api/v1/analytics/signals (signals feed — used by poupi-crypto)
```
Query params:
  symbol      string  required  e.g. BTC/USDT
  timeframe   string  required  e.g. 15m | 1h
  since_hours int     optional  default 24
  limit       int     optional  default 100 max 500

Response: list of analytics objects:
[{
  "id": "uuid",
  "symbol": "BTC/USDT",
  "timeframe": "15m",
  "timestamp": "2026-05-16T02:19:40Z",
  "signal": "HOLD",
  "confidence": 34,
  "regime": "TRENDING_UP",
  "rsi": 56.79,
  "adx": 26.18,
  "atr": 87.69,
  "moving_average_fast": 2228.5,
  "moving_average_slow": 2220.1,
  "volume_ratio": 1.12,
  "breakout_score": 25.0,
  "trend_score": 0.34,
  "calculated_at": "2026-05-16T02:19:40.737Z"
}]
```

### GET /api/v1/crypto/feed (candles feed — used by poupi-crypto)
```
Query params:
  symbol      string  required
  timeframe   string  optional  default 1h
  since_hours int     optional  default 24
  limit       int     optional  default 100 max 500

Response: list of OHLCV candles:
[{
  "id": "uuid",
  "symbol": "BTC/USDT",
  "timeframe": "15m",
  "timestamp": "2026-05-16T02:00:00Z",
  "open": 79100.0,
  "high": 79250.0,
  "low": 79050.0,
  "close": 79190.85,
  "volume": 1234.5,
  "source": "crypto_coin_exchange"
}]
```

---

## Real Estate module — `/api/v1/real-estate`

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/real-estate/listings` | Normalized listings with optional filters |
| GET | `/api/v1/real-estate/analytics` | Analytics (price/m2, opportunity score) |

Query params: `city`, `listing_type` (sale\|rent), `property_type`, `min_price`, `max_price`, `limit`

---

## Sports Odds module — `/api/v1/sports-odds`

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/sports-odds/odds` | Normalized odds with optional filters |
| GET | `/api/v1/sports-odds/analytics` | Line movement and CLV analytics |

Query params: `sport`, `league`, `sportsbook`, `since_hours`, `limit`

---

## Price Feed (legacy ecommerce) — `/api/v1/price-feed`

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/price-feed` | Normalized products with cursor-based pagination |

Query params: `store_name`, `category`, `cursor` (ISO timestamp), `limit`

---

## Raw data + Pipeline — `/api/v1/raw`

| Method | Path | Description |
|---|---|---|
| POST | `/api/v1/raw/save` | Save raw collection (used internally by collectors) |
| GET | `/api/v1/raw/pending` | List pending raw records |
| GET | `/api/v1/raw/{id}` | Get specific raw record |

---

## Data Quality — `/api/v1/data-quality`

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/data-quality/runs` | Data quality check run history |
| POST | `/api/v1/data-quality/run` | Trigger data quality check |

---

## Documentation / Lineage — `/api/v1/docs`

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/docs/lineage/{raw_id}` | Full lineage: raw → normalized → analytics |
| GET | `/api/v1/docs/schemas` | Registered schema documentation |
| GET | `/api/v1/docs/collectors` | Registered collector documentation |

---

## Response conventions

- All IDs are UUIDs (string)
- Timestamps: ISO 8601 with timezone (`2026-05-16T02:19:40.737816+00:00`)
- Prices: float (use `numeric` in DB for precision)
- Errors: `{"detail": "error message"}` with appropriate HTTP status
- Pagination: cursor-based (ISO timestamp) or `limit`/`offset`

## Status codes used
| Code | Meaning |
|---|---|
| 200 | OK |
| 201 | Created |
| 400 | Bad request / validation error |
| 401 | Missing or invalid API key |
| 404 | Resource not found |
| 429 | Rate limit exceeded |
| 503 | Service unavailable (readiness probe only) |
