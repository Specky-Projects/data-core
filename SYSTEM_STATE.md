# SYSTEM STATE - data-core operational truth

Audit timestamp: 2026-05-25 America/Sao_Paulo (updated: Phase RELIABILITY).

## Classification

System state: DEGRADED.

Production readiness: NO-GO.

## Runtime

- Docker: responsive.
- API: READY.
- Postgres: READY.
- Redis: ADVISORY_ONLY, up but `CACHE_ENABLED=false`.
- Scheduler: READY.
- Worker: READY.
- RestartCount: 0 for API/scheduler/worker/Postgres.
- OOMKilled: false for API/scheduler/worker/Postgres.

## Endpoints

- `/health`: OK.
- `/system-status`: DEGRADED.
- `/health/business`: DEGRADED.
- `/ready`: 503.

This is the intended behavior because `/ready` cannot be green while ecommerce providers remain blocked.

## Crypto data flow

Final flow:

- Fresh collection exists.
- Normalization is active.
- Analytics is active.
- Backlog is drained/classified.

Counts:

- Raw crypto ignored: 557.
- Raw crypto normalized: 57051.
- Raw crypto pending: 0.
- Raw crypto failed: 0.

Ignored classification:

- 557/557 ignored rows match existing normalized candles by source, symbol, timeframe and timestamp.
- They are idempotency/dedup outcomes.

## Ecommerce

- Pague Menos: READY.
- Drogasil: BLOCKED by `HTTP_403_FORBIDDEN`.
- Droga Raia: BLOCKED by `HTTP_403_FORBIDDEN`.

No scraping strategy or anti-bot bypass changed.

## Observability

- `/system-status` exposes DEGRADED status and provider details.
- `/metrics` exposes DB-backed pipeline metrics.
- Watchdog no longer treats probe boot count as Docker restart truth.
- Scheduler watchdog is healthy.

## Disk

Disk C: remains an operational risk.

Evidence:

- C: has roughly 561 MB free.
- Docker images: 22.4 GB, 15 GB reclaimable.
- Docker build cache: 12.1 GB, all reclaimable.
- Docker data VHDX: about 27.9 GB.

No cleanup was executed.

## Tests

- `tests/test_scheduler_watchdog.py`: 18 passed.
- Test hang root cause was global Prometheus registry exposition after DB-backed metrics were added.
- Test now validates watchdog gauges directly.

## Reliability layer (Phase RELIABILITY — 2026-05-25)

New capabilities active:
- Pipeline liveness registry: RUNNING/DEGRADED/STALLED/BLOCKED/DEAD per pipeline
- Scheduler proof-of-execution heartbeat: `runtime-data/scheduler_heartbeat.json`
- Dead pipeline detector: detects backlog-growing + normalize-static within 20 min
- Self-healing coordinator: bounded advisory recovery (3 triggers/h/pipeline max)
- Backlog recovery engine: adaptive batch sizing under DB pressure
- Env drift detection: `scripts/audit_runtime_env.py` (exit 1 on SCHEDULER_PIPELINE_ENABLED=false)
- 7 Grafana dashboards + 12 Prometheus alert rules
- `/system-status` now exposes `pipelines` and `scheduler.heartbeat` sections

Scheduler silent-stall detection window: ≤ 10 min (heartbeat STALLED threshold).

## READY criteria still missing

1. Ecommerce provider coverage must be resolved or readiness policy must explicitly accept partial provider coverage.
2. Disk C: pressure must be reduced.
3. `/ready` must remain 503 until `/system-status.status=READY`.
4. Run `python scripts/audit_runtime_env.py` before every production deploy.
