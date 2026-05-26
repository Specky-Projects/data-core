# CURRENT RUNTIME STATE

Timestamp: 2026-05-25 America/Sao_Paulo.

## Decision

DEGRADED.

The runtime and crypto pipeline are recovered. Production readiness remains NO-GO.

## Current runtime

- Docker: stable and responsive.
- API: healthy.
- Postgres: healthy and SQL-ready.
- Redis: healthy, advisory-only because cache is disabled.
- Scheduler: healthy.
- Worker: healthy with fresh heartbeat.
- Restart count: 0 for API/scheduler/worker/Postgres.
- OOMKilled: false for API/scheduler/worker/Postgres.

## Endpoint state

- `/health`: 200.
- `/system-status`: DEGRADED.
- `/health/business`: DEGRADED.
- `/ready`: 503, correct while system is DEGRADED.

## Pipeline state

- Crypto pending backlog: 0.
- Crypto failed normalization: 0.
- Crypto ignored/deduplicated: 557.
- Crypto normalized: 57051.
- Latest raw: 2026-05-25T10:56:43Z.
- Latest normalized: 2026-05-25T10:52:28Z.
- Latest analytics: 2026-05-25T10:52:34Z.

## Provider state

- Pague Menos: READY.
- Drogasil: BLOCKED, `HTTP_403_FORBIDDEN`.
- Droga Raia: BLOCKED, `HTTP_403_FORBIDDEN`.

## Operational risks

1. Ecommerce provider coverage remains partial.
2. Disk C: remains critically low.
3. Docker VHDX/build cache/images are large, but no prune was executed.

## Reliability layer state (Phase RELIABILITY — 2026-05-25)

- `app/pipeline/liveness.py`: 10 pipelines tracked, cached in `runtime-data/pipeline_liveness.json`
- `app/runtime/scheduler_heartbeat.py`: proof-of-execution, written by scheduler every 5 min
- `app/pipeline/self_healing.py`: bounded recovery, audit at `runtime-data/self_healing_log.jsonl`
- `scripts/audit_runtime_env.py`: env drift detection — run before deploy
- Alert rules: `prometheus/rules/pipeline_reliability_alerts.yml`
- Dashboards: `grafana/dashboards/pipeline_liveness.json`, `scheduler_reliability.json`, `queue_lag.json`, `backlog_recovery.json`, `self_healing.json`, `runtime_drift.json`, `pipeline_freshness.json`

New `/system-status` sections: `pipelines` (liveness), `runtime.scheduler.heartbeat` (heartbeat).

## Suggested safe cleanup path

Review and approve explicit Docker cleanup separately:

- remove unused build cache only;
- remove unused images only after confirming they are not needed;
- do not remove volumes;
- do not prune all resources blindly.

## Scheduler forensics 6h+ checkpoint - 2026-05-25T18:17Z

Observation time since scheduler image start: `7.6232` hours.

Window status: time gate met, runtime stability gate failed.

Evidence available from local JSONL before runtime/API became unreachable:

- Post-deploy dry-run decisions: `0`.
- Drift events: `5`.
- Drift average: `19.1258026` seconds.
- Drift max: `54.772003` seconds.
- Drift by job:
  - `collector:crypto.crypto_coin_ohlcv`: `2` events, max `54.772003`.
  - `maintenance:cleanup_stale_runs`: `2` events, max `0.217407`.
  - `platform:operational_watchdog`: `1` event, max `5.745624`.
- Lifecycle events exist through `scheduler_started`.
- Last watchdog snapshot:
  - timestamp `2026-05-25T11:21:14.548261+00:00`.
  - `restart_count_source=probe_only`.
  - `observed_restart_count=0`.
  - `oom_kill_count=0`.
  - `oom_recent=false`.
  - `swap_usage_bytes=0`.
  - `memory_usage_bytes=385069056`.
  - `heartbeat_sequence=81`.
  - `trend_state=MEMORY_GROWING`.
- Snapshot age at checkpoint: `24961.104` seconds.

Runtime/API state at checkpoint:

- Docker API unavailable: `dockerDesktopLinuxEngine` pipe missing.
- `GET /health` failed: remote server unreachable.
- `localhost:8000` TCP test failed.
- `/system-status` and `/metrics` could not be queried live.

Decision:

- Watchdog observability: NO-GO for final 6h validation because heartbeat is stale and API/Docker runtime is unavailable.
- Scheduler forensics: PARTIAL. Drift persistence is proven, but the continuous window did not remain observable.
- Runtime protection: NO-GO.
- Trading/live changes: NO-GO.

## Scheduler forensics final checkpoint - 2026-05-25T21:17Z

Observation time since scheduler image start: `10.6238` hours.

Window status: time gate met, final validation remains `NO-GO`.

Read-only checks:

- Docker API unavailable: `dockerDesktopLinuxEngine` pipe missing.
- `GET /health`: failed, remote server unreachable.
- `GET /system-status`: failed, remote server unreachable.
- `GET /metrics`: failed, remote server unreachable.

Local JSONL evidence:

- Post-deploy dry-run decisions: `0`.
- Drift events: `5`.
- Drift average: `19.1258026` seconds.
- Drift max: `54.772003` seconds.
- Drift by job:
  - `collector:crypto.crypto_coin_ohlcv`: `2` events, max `54.772003`.
  - `maintenance:cleanup_stale_runs`: `2` events, max `0.217407`.
  - `platform:operational_watchdog`: `1` event, max `5.745624`.
- Last watchdog snapshot:
  - timestamp `2026-05-25T18:31:59.620710+00:00`.
  - snapshot age at checkpoint: `9918.072` seconds.
  - `restart_count_source=probe_only`.
  - `observed_restart_count=0`.
  - `probe_boot_count=10`.
  - `oom_kill_count=0`.
  - `oom_recent=false`.
  - `swap_usage_bytes=0`.
  - `memory_usage_bytes=225144832`.
  - `heartbeat_sequence=2`.
  - `trend_state=MEMORY_SPIKING`.
- Lifecycle shows repeated scheduler process starts after Docker/API became unavailable:
  - `probe_boot_count=8` at `2026-05-25T18:20:56Z`.
  - `probe_boot_count=9` at `2026-05-25T18:26:39Z`.
  - `probe_boot_count=10` at `2026-05-25T18:31:29Z`.

Interpretation:

- Drift persistence is proven.
- Restart-loop false positive did not return: `observed_restart_count=0`, source remains `probe_only`.
- Continuous observability failed because Docker/API are unavailable and heartbeat is stale.
- Repeated lifecycle process starts require Docker/Desktop/host-runtime investigation before any reliability activation.

Final decision:

- Watchdog observability: NO-GO for extended validation.
- Scheduler forensics: PARTIAL; drift and lifecycle files work, but continuous runtime observability failed.
- Runtime protection: NO-GO.
- Trading/live changes: NO-GO.

## Server runtime audit - 2026-05-25

Decision: DEGRADED.

The notebook remains DEV/debug only. Always-on ownership is moving to the server, but the server is not yet READY for additional production-critical load.

Server evidence:

- Host: `poupi` / `65.109.239.250`.
- CPU/RAM: 2 vCPU, 3.7 GiB RAM.
- Swap: about 676 MiB of 1.0 GiB used.
- Disk: root 82% used, 6.6 GiB free.
- Extra volume: `/mnt/HC_Volume_105715453`, 9.3 GiB free.
- Docker: Engine 29.5.0, Compose v5.1.3.

Running server workloads:

- data-core API: running, Docker health `healthy`.
- data-core scheduler: running, no Docker healthcheck, about 593 MiB of 768 MiB.
- data-core worker: running, no Docker healthcheck.
- poupi-crypto API: running, Docker health `healthy`, `/health` 200.
- poupi-crypto Postgres: running, Docker health `healthy`.
- poupi-baby current Coolify app: running.
- Prometheus: running, `/-/ready` 200, `/-/healthy` 200.
- Alertmanager: running, `/-/ready` 200, `/-/healthy` 200.
- Grafana: running, Docker health `healthy`.

Prometheus targets:

- data-core-api: UP.
- poupi-baby-backend: UP.
- poupi-crypto-api: UP.
- poupi-jobs-api: UP.

Operational risks:

1. Prometheus is bound publicly on `0.0.0.0:9090`.
2. `poupi-crypto` Postgres is bound publicly on `0.0.0.0:5435`.
3. `ufw` was not installed during audit.
4. Scheduler memory pressure is high.
5. Root disk pressure is high.
6. Backups were not evidenced by the read-only backup scan.

GO/NO-GO:

- Notebook DEV-only: GO.
- Existing server observability: DEGRADED.
- Existing server runtime: DEGRADED.
- Adding more always-on load: NO-GO.
- Database migration: NO-GO until backup and restore test.
- Live trading: NO-GO.

## Server hardening result - 2026-05-25/26

Decision: DEGRADED, improved security posture.

Applied:

- Public exposure guard for Docker-published admin/data ports.
- External Prometheus `9090` blocked.
- External `poupi-crypto` Postgres `5435` blocked.
- Docker log rotation policy installed.
- Server backup created on mounted extra volume.
- PostgreSQL restore test completed in isolated temporary container.

Post-hardening validation:

- External `9090`: unreachable.
- External `5435`: unreachable.
- SSH, HTTP, HTTPS, and `8002` remained reachable.
- Prometheus local `/-/ready`: 200.
- Prometheus local `/-/healthy`: 200.
- Alertmanager local `/-/ready`: 200.
- Alertmanager local `/-/healthy`: 200.
- Prometheus targets: 4 total, 4 UP.
- `poupi-crypto-db-1`: `pg_isready` OK internally.
- Grafana container health: healthy.
- No running container reported `OOMKilled=true`.

Resource state:

- Root disk improved from 82% used to 58% used.
- Docker build cache reported `0B` after final validation; no destructive prune command was executed.
- Swap remains critical at about 916 MiB of 1 GiB used.
- Scheduler memory remains high, about 576 MiB of 768 MiB.

Backup state:

- Backup root: `/mnt/HC_Volume_105715453/poupi-backups/20260525T205906Z`.
- Backup size: 79M.
- Restore test: PASS, 11 PostgreSQL dumps restored with `--no-owner --no-acl`.

GO/NO-GO:

- Runtime server: DEGRADED, improved.
- Observability: DEGRADED, improved.
- Add always-on load: NO-GO.
- Database migration: NO-GO until recurring backup and restore runbook.
- Production readiness: NO-GO.
- Paper trading: NO-GO pending explicit operational approval.
- Live trading: ABSOLUTE NO-GO.

## Scheduler forensics passive window - final 2026-05-26T17:02Z

Window status: elapsed time gate met, final validation remains `NO-GO`.

Evidence:

- Elapsed time since controlled API/scheduler deploy: `30.3722` hours.
- Post-deploy dry-run decisions: `3`.
- Post-deploy decision modes: `NORMAL=3`.
- Drift persistence is proven: `68` events in `runtime-data/scheduler_execution_drift.jsonl`.
- Average drift: `8.634050411764704` seconds.
- Max drift: `54.772003` seconds on `collector:crypto.crypto_coin_ohlcv`.
- Drift events by job:
  - `platform:scheduler_heartbeat`: `33`, max `0.130205`.
  - `collector:crypto.crypto_coin_ohlcv`: `13`, max `54.772003`.
  - `maintenance:cleanup_stale_runs`: `13`, max `0.365494`.
  - `platform:operational_watchdog`: `6`, max `5.745624`.
  - `maintenance:alert_webhook`: `2`, max `2.56297`.
  - `ecommerce:url_scraper_targets`: `1`, max `0.469531`.
- Latest watchdog snapshot timestamp: `2026-05-26T14:29:10.519324+00:00`.
- Snapshot age at checkpoint: `9181.4` seconds.
- Latest restart provenance: `restart_count_source=probe_only`.
- `observed_restart_count=0`.
- `oom_kill_count=0`.
- `swap_usage_bytes=0`.
- `trend_state=MEMORY_STABLE`.

Failure condition:

- `docker compose ps api scheduler` returned no active service rows.
- `data-core-api-1`: `status=exited`, `health=unhealthy`, `restartCount=0`, `OOMKilled=false`.
- `data-core-scheduler-1`: `status=exited`, `health=unhealthy`, `restartCount=0`, `OOMKilled=false`.
- `GET /health`, `GET /system-status`, and `GET /metrics` failed because `localhost:8000` was unreachable.

GO/NO-GO:

- Watchdog observability: NO-GO for continuous runtime validation because endpoints are down and heartbeat is stale.
- Scheduler forensics: PARTIAL; lifecycle and drift files are emitted, but the runtime did not remain healthy.
- Runtime protection: NO-GO.
- Trading/live changes: NO-GO.
