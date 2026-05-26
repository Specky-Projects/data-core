# Observability Migration Report

Date: 2026-05-25

## Scope

Observability components:

- Prometheus
- Grafana
- Alertmanager

This report records the current server state and the controlled path to make server observability production-ready.

No metrics, dashboards, rules, datasets, or runtime behavior were deleted or reset.

## Current State

| Component | Container | Status | Endpoint Check | Persistence | Risk |
| --- | --- | --- | --- | --- | --- |
| Prometheus | `prometheus` | running | `/-/ready` 200, `/-/healthy` 200 | `prometheus-data` | Public `0.0.0.0:9090` |
| Grafana | `grafana-q11p1efg13of6ujrfgu25lal` | running, healthy | Container health healthy | `q11p1efg13of6ujrfgu25lal_grafana-data` | Auth/TLS path must be reviewed |
| Alertmanager | `alertmanager` | running | `/-/ready` 200, `/-/healthy` 200 | Compose/config dependent | Local `127.0.0.1:9093` |

## Prometheus Targets

All active targets were UP during the audit:

| Job | Health | Scrape URL |
| --- | --- | --- |
| data-core-api | up | `http://data-core-api:8000/metrics` |
| poupi-baby-backend | up | `http://poupi-baby-backend:3001/metrics` |
| poupi-crypto-api | up | `http://poupi-crypto-api:8002/metrics` |
| poupi-jobs-api | up | `http://poupi-jobs-api:8001/metrics/` |

## Volumes

- Prometheus data: `prometheus-data`, about 71.72 MB in the Docker inventory.
- Grafana data: `q11p1efg13of6ujrfgu25lal_grafana-data`, about 54.12 MB in the Docker inventory.

These volumes are KEEP. Do not prune, recreate, or replace them without backup and approval.

## Security Findings

- Prometheus is bound to `0.0.0.0:9090`.
- `ufw` was not installed during the audit.
- Traefik is publicly bound on `80`, `443`, and `8080`.
- Alertmanager is local-only on `127.0.0.1:9093`.

## Migration Status

Observability is already present on the server, but production readiness is DEGRADED.

This is not a clean final migration until:

- Prometheus is protected from public access.
- Grafana auth, TLS, and admin credentials are reviewed.
- Alertmanager receivers and webhook secrets are verified.
- Dashboards and alert rules are backed up/exported.
- Retention settings are documented.
- Backups are stored outside the root filesystem, preferably on `/mnt/HC_Volume_105715453` or external storage.

## Backup Plan

Before any redeploy or migration:

1. Export Grafana dashboards and datasources.
2. Back up `q11p1efg13of6ujrfgu25lal_grafana-data`.
3. Snapshot or tar `prometheus-data`.
4. Copy Prometheus rules and scrape configs.
5. Copy Alertmanager config and receiver templates.
6. Store checksums and backup timestamp.
7. Perform a restore rehearsal into a temporary non-public stack.

## Rollback Plan

Rollback trigger:

- Grafana unreachable.
- Prometheus target coverage drops unexpectedly.
- Alertmanager cannot load config.
- Alerting receiver secrets missing.
- Data volume mount mismatch.

Rollback action:

1. Stop only the new observability deployment.
2. Reattach the previous volumes/configs.
3. Restore previous compose/Coolify revision.
4. Validate `/-/ready`, `/-/healthy`, Prometheus targets, Grafana dashboards, and Alertmanager status.
5. Keep notebook observability disabled unless explicitly approved for emergency fallback.

## Decision

- Observability on server: DEGRADED.
- Cutover from notebook to server: GO for keeping notebook DEV-only, because notebook observability is already disabled.
- Production-ready observability: NO-GO until public exposure, backups, and dashboard/rule export are fixed.
