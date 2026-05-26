# CURRENT STATUS - data-core operational truth

Audit timestamp: 2026-05-25 America/Sao_Paulo (updated: Phase RELIABILITY).
Repository: `C:\Users\dev\Documents\Projetos\data-core`.

## Executive summary

Final operational decision: DEGRADED.

Production readiness: NO-GO.

Docker, Postgres, API, scheduler and worker are stable. Crypto collection is fresh again, crypto backlog is drained/classified, normalization/analytics are recent, and `/ready` remains honest by returning 503 while ecommerce providers are blocked.

The system is not READY because two ecommerce providers remain blocked by `HTTP_403_FORBIDDEN`, only Pague Menos is healthy, and host disk C: remains critically low.

## Runtime evidence

- `docker compose ps`: API, Postgres, Redis, scheduler and worker are running and healthy.
- Docker inspect: API/scheduler/worker/Postgres `RestartCount=0`, `OOMKilled=false`.
- Postgres SQL handshake works.
- `/health`: 200.
- `/system-status`: `DEGRADED`.
- `/ready`: 503 with `operational=DEGRADED`.
- Worker heartbeat: fresh.
- Scheduler watchdog: healthy; probe boot count is diagnostic only.
- Redis: `up=true`, `used=false`, `readiness_requires_redis=false`.

## Crypto pipeline

Backlog:

- Initial phase backlog: 1171.
- After first recovery: 471.
- After final controlled batches: 0 pending.

Final crypto status:

- `ignored`: 557.
- `normalized`: 57051.
- `normalization_pending`: 0.
- `normalization_failed`: 0.

Classification:

- 557/557 ignored crypto raws match existing normalized market candles by source, symbol, timeframe and timestamp.
- These are classified as idempotent/deduplicated candles, not deleted backlog.

Freshness:

- Latest crypto raw: 2026-05-25T10:56:43Z.
- Latest crypto normalized timestamp: 2026-05-25T10:52:28Z.
- Latest trading analytics timestamp: 2026-05-25T10:52:34Z.

Final fresh collection evidence:

- `crypto.crypto_coin_ohlcv` run at 2026-05-25T10:56:08Z succeeded.
- `raw_saved_count=10`.
- Those 10 raws were classified as skipped/deduplicated by normalization.

## Readiness

`/system-status` final degraded reason:

- `ecommerce_providers_blocked`.

`collection_readiness.ready=true` in `/system-status` after backlog drain, but business readiness remains DEGRADED because provider coverage is not healthy.

`/ready` remains 503. This is correct.

## Ecommerce providers

- Pague Menos: READY/functional.
- Drogasil: BLOCKED, `HTTP_403_FORBIDDEN`.
- Droga Raia: BLOCKED, `HTTP_403_FORBIDDEN`.

No anti-bot bypass or scraping strategy change was made.

## Disk risk

Disk C: remains critically low, around 561 MB free in the final measurement.

Docker disk evidence:

- Docker images: 22.4 GB total, 15 GB reclaimable.
- Docker build cache: 12.1 GB total, 12.1 GB reclaimable.
- Docker Desktop VHDX: `C:\Users\dev\AppData\Local\Docker\wsl\disk\docker_data.vhdx`, about 27.9 GB.

No prune or destructive cleanup was executed.

## Tests

- `python -m pytest tests\test_scheduler_watchdog.py -q`: 18 passed in 0.76s.
- Previous hang was isolated to a test using global Prometheus `generate_latest()` after DB-backed metrics were added. The test now validates watchdog gauges directly.

## Phase RELIABILITY — implemented 2026-05-25

Root cause resolved: `SCHEDULER_PIPELINE_ENABLED=false` → `normalize_job` never scheduled.

New components:
- `app/pipeline/liveness.py` — 10 pipelines with RUNNING/DEGRADED/STALLED/BLOCKED/DEAD states
- `app/runtime/scheduler_heartbeat.py` — proof-of-execution heartbeat (not container-UP)
- `app/pipeline/self_healing.py` — bounded, non-destructive recovery (max 3 triggers/h/pipeline)
- `scripts/audit_runtime_env.py` — env drift detection (exit 1 on critical drift)
- `scripts/soak_reliability_test.py` — 6h/12h/24h soak validation
- 7 Grafana dashboards in `grafana/dashboards/`
- `prometheus/rules/pipeline_reliability_alerts.yml` — 12 new alerting rules
- `/system-status` expanded: `pipelines`, `scheduler.heartbeat` sections

New `feed.status` semantics in poupi-baby `health.service.ts`:
- `ok` = data-core UP + data flowing
- `degraded` = data-core UP but pipeline stalled
- `critical` = data-core unreachable

No business logic, scraping logic, anti-bot bypass, Telegram publishing, SEO generation, pricing strategy, or DRY_RUN settings were changed.

## Final classification

Runtime: GO.

Crypto pipeline: GO.

Pipeline reliability: READY (liveness auditável, scheduler heartbeat real, self-healing seguro).

Production readiness: NO-GO.

Overall: DEGRADED, because ecommerce provider coverage and disk pressure remain unresolved.
## Local Runtime Policy - 2026-05-25

The local notebook must no longer operate as a mini-production runtime.

Local-only compose overrides were introduced for the Poupi repos:

- `data-core/docker-compose.local.yml`
- `poupi-baby/docker-compose.local.yml`
- `poupi-crypto/docker-compose.local.yml`
- `poupi-frontend/docker-compose.local.yml`

The overrides keep production compose files unchanged, set local
`restart: "no"`, and require explicit Compose profiles for runtime,
observability, scheduler, worker, dev, and debug use cases.

Existing local containers may still have `unless-stopped` until their local
Docker restart policy is updated or the containers are recreated with the local
override. No volumes, databases, datasets, strategy, trading runtime, or env
values were changed by this policy.

## Server Runtime Migration Audit - 2026-05-25

Server `poupi` (`65.109.239.250`) was audited read-only for always-on runtime migration.

Result: DEGRADED.

Evidence:

- CPU/RAM: 2 vCPU, 3.7 GiB RAM.
- Swap pressure: about 676 MiB of 1.0 GiB used.
- Disk pressure: root filesystem 82% used, 6.6 GiB free.
- Extra mounted volume: `/mnt/HC_Volume_105715453`, 9.3 GiB free.
- Docker: Engine 29.5.0, Compose v5.1.3.
- Prometheus, Grafana, Alertmanager are already running on the server.
- Prometheus targets are UP for data-core API, poupi-baby backend, poupi-crypto API, and poupi-jobs API.
- data-core API/scheduler/worker are running on the server.
- poupi-crypto API and DB are running on the server.
- poupi-baby current Coolify app is running; legacy poupi-baby compose containers are stopped and preserved.
- No container reported `OOMKilled=true` during the audit.

Risks:

- Prometheus is publicly exposed on `0.0.0.0:9090`.
- `poupi-crypto` Postgres is publicly exposed on `0.0.0.0:5435`.
- `ufw` was not installed during audit.
- data-core scheduler is close to its memory limit.
- No backup artifact was found in `/data` or `/mnt/HC_Volume_105715453` during the read-only scan.

Decision:

- Notebook DEV-only: GO.
- Existing server runtime: DEGRADED.
- Existing server observability: DEGRADED.
- Adding more always-on load: NO-GO until capacity, backups, and port exposure are remediated.
- Live trading: NO-GO.

## Server Hardening - 2026-05-25/26

Controlled hardening was executed on server `poupi`.

Changes applied:

- Persistent public exposure guard installed via `poupi-docker-user-firewall.service`.
- Public ingress to Prometheus `9090` blocked.
- Public ingress to `poupi-crypto` Postgres `5435` blocked.
- Docker JSON log rotation installed at `/etc/logrotate.d/poupi-docker-json-logs`.
- Real backup created on `/mnt/HC_Volume_105715453`.
- Isolated PostgreSQL restore test completed successfully.

Validation:

- External `9090`: unreachable.
- External `5435`: unreachable.
- SSH `22`: reachable.
- HTTP `80`: reachable.
- HTTPS `443`: reachable.
- Public crypto API `8002`: reachable.
- Prometheus local ready/healthy: 200/200.
- Alertmanager local ready/healthy: 200/200.
- Prometheus targets: 4/4 UP.
- `poupi-crypto-db-1`: `pg_isready` OK internally.
- No current running container reported `OOMKilled=true`.

Backup:

- Backup root: `/mnt/HC_Volume_105715453/poupi-backups/20260525T205906Z`.
- Backup size: 79M.
- Restore test: PASS, 11 PostgreSQL dumps restored in a disposable container.

Current risks:

- Swap remains critical at about 916 MiB of 1 GiB used.
- Coolify/Traefik public ports `8000`, `8080`, `6001`, `6002` still require review.
- Scheduler memory remains high.
- Some runtime containers lack Docker healthchecks.
- Server is safer, but still not production-ready.

Decision:

- Runtime server: DEGRADED, improved.
- Observability: DEGRADED, improved.
- Adding new always-on load: NO-GO.
- Database migration: NO-GO until recurring backup/restore runbook is approved.
- Production readiness: NO-GO.
- Paper trading: NO-GO pending explicit review.
- Live trading: ABSOLUTE NO-GO.
