# Runtime Migration Plan

Date: 2026-05-25

## Scope

This plan moves always-on runtime ownership to the server while keeping the notebook as DEV/debug only.

The plan does not alter:

- Strategy
- Thresholds
- DRY_RUN or live trading
- Execution engine
- Sizing
- Risk logic
- SL/TP
- Scraping logic
- Anti-bot behavior
- Quantitative datasets
- Decision rules

## Current Position

The notebook has already been converted to local on-demand mode with `docker-compose.local.yml` and Compose profiles.

The server already runs several always-on workloads:

- data-core API, scheduler, worker
- poupi-baby app through a Coolify deployment
- poupi-crypto API and Postgres
- Prometheus, Grafana, Alertmanager
- Shared Postgres and Redis infrastructure

The migration is therefore a controlled hardening and ownership transfer, not a blind first deploy.

## Server Capacity Gate

Current classification: DEGRADED.

Observed constraints:

- 2 vCPU and 3.7 GiB RAM.
- Swap at about 676 MiB of 1.0 GiB.
- Root disk at 82%.
- Scheduler using about 593 MiB of a 768 MiB limit.
- Docker build cache and inactive images exist, but no prune is approved by this plan.

Required before adding workload:

1. Decide whether to resize server RAM or reduce service memory limits.
2. Move backups/log archives to `/mnt/HC_Volume_105715453` or external storage.
3. Reduce root disk pressure with an approved Docker cleanup plan.
4. Protect public ports.
5. Prove backups and restore.

## Migration Phases

### Phase 0 - Freeze Local Always-On

Status: DONE.

- Keep notebook Docker containers stopped by default.
- Keep local restart policies as `no`.
- Use local Compose profiles only for dev/debug/manual runtime.
- Do not run local schedulers/workers while server schedulers/workers are active.

### Phase 1 - Observability Hardening

Goal: make existing server observability safe.

Steps:

1. Export Grafana dashboards/datasources.
2. Back up Grafana and Prometheus volumes.
3. Back up Prometheus rules and Alertmanager config.
4. Restrict Prometheus `9090` and database ports from public access.
5. Validate TLS/auth path for Grafana.
6. Validate Prometheus target coverage.
7. Validate Alertmanager receiver secrets and routing.

Rollback:

- Restore previous volumes/configs and previous Coolify/Compose revision.
- Validate Prometheus `/-/ready`, Grafana health, targets UP, and Alertmanager health.

Decision gate:

- GO only after backups and public exposure remediation.

### Phase 2 - Runtime Ownership

Goal: server is the only always-on runtime owner.

Services:

- data-core API
- data-core scheduler
- data-core worker
- poupi-baby backend
- poupi-baby worker
- poupi-crypto API/workers
- Redis/Postgres dependencies

Steps:

1. Record currently active server containers, images, env sources, networks, volumes, and restart policies.
2. Confirm notebook has no running local scheduler/worker/API containers.
3. Validate `/health`, `/ready`, `/system-status`, `/metrics`.
4. Validate scheduler heartbeat and worker heartbeat.
5. Validate queue/backlog/freshness.
6. Validate no duplicate scheduler execution.
7. Keep all restart policies explicit and documented.

Rollback:

- Stop only the failed server revision.
- Restore previous image tag/revision.
- Reattach previous volumes.
- Do not start notebook fallback unless duplicate execution risk is explicitly accepted and schedulers are disabled on one side.

Decision gate:

- GO for existing server runtime monitoring.
- NO-GO for expanding workload until server capacity/security gates pass.

### Phase 3 - Persistence and Backups

Goal: protect state before any database movement.

Items:

- Postgres volumes
- Redis persistence
- Runtime data
- Signal datasets
- Replay datasets
- Prometheus data
- Grafana data

Steps:

1. Inventory every persistent volume and bind mount.
2. Create logical database dumps where applicable.
3. Create volume-level backups.
4. Store backups away from the root filesystem.
5. Test restore into temporary isolated services.
6. Record checksums and restore commands.

Rollback:

- Restore from tested backup only.
- Never overwrite a live production volume without stopping the dependent service and confirming target identity.

Decision gate:

- Database migration: NO-GO until backup and restore test are completed.

### Phase 4 - Security

Goal: remove accidental public exposure.

Required changes:

- Restrict `9090`.
- Restrict `5435`.
- Review Coolify/Traefik `8080`, `8000`, `6001`, and `6002`.
- Ensure Grafana is behind TLS/auth.
- Keep secrets out of Git.
- Review env sources in Coolify before exporting or copying.

Rollback:

- Restore previous firewall/routing rules only if service loss is worse than exposure risk.
- Prefer SSH tunnel/VPN for admin endpoints.

## Validation Checklist

Run after each migration or redeploy:

- `docker ps`
- `docker inspect` restart policy and OOM status
- `docker stats --no-stream`
- `/health`
- `/ready`
- `/system-status`
- `/metrics`
- Prometheus targets
- Grafana dashboards
- Alertmanager status
- Scheduler heartbeat
- Worker heartbeat
- Queue/backlog/freshness
- Disk, RAM, and swap
- Logs for restart loops

## GO / NO-GO

| Area | Decision | Reason |
| --- | --- | --- |
| Notebook DEV-only | GO | Local restart policies/profiles already prevent automatic mini-production |
| Server observability | DEGRADED | Running and targets UP, but Prometheus is public and backups are not proven |
| Server runtime | DEGRADED | Running, but capacity/security/backups need hardening |
| Add more always-on services | NO-GO | RAM/swap/disk/security gates not met |
| Database migration | NO-GO | Backup and restore test not yet proven |
| Paper trading | NO-GO pending runtime/business readiness review | Must be approved separately |
| Live trading | NO-GO | Explicitly out of scope |
