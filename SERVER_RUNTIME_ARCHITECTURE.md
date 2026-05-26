# Server Runtime Architecture

Date: 2026-05-25

## Scope

This document describes the target always-on server architecture for the Poupi platform.

No trading, strategy, sizing, risk, SL/TP, scraping, anti-bot, dataset, or production env behavior is changed by this document.

## Current Server

- Host: `poupi` / `65.109.239.250`
- OS: Ubuntu Linux, kernel `6.8.0-111-generic`
- CPU: 2 vCPU
- RAM: 3.7 GiB
- Swap: 1.0 GiB
- Root disk: 38 GiB, 30 GiB used, 6.6 GiB free, 82% used
- Extra mounted volume: `/mnt/HC_Volume_105715453`, 9.8 GiB total, 9.3 GiB free
- Docker Engine: 29.5.0
- Docker Compose: v5.1.3
- Firewall: `ufw` not installed during audit

## Classification

Server state: DEGRADED.

The server is already running observability and runtime workloads, but it is not cleanly READY for further always-on expansion without capacity and security hardening.

Primary risks:

- Swap usage is high: about 676 MiB of 1.0 GiB.
- Root disk is high: 82% used with 6.6 GiB free.
- Prometheus is publicly exposed on `0.0.0.0:9090`.
- `poupi-crypto` Postgres is publicly exposed on `0.0.0.0:5435`.
- Scheduler memory is close to its limit: about 593 MiB of 768 MiB.
- No backup artifact was found in `/data` or `/mnt/HC_Volume_105715453` during the read-only scan.

## Current Always-On Containers

| Service | Container | Status | Health | Restart | Notes |
| --- | --- | --- | --- | --- | --- |
| poupi-baby app | `dfmhxr9vn96wxbno98b0i1ik-161150868477` | running | none | unless-stopped | Port 3001 internal |
| poupi-crypto API | `poupi-crypto-api-1` | running | healthy | unless-stopped | Public `8002` |
| data-core scheduler | `scheduler-dvq6dwsagsw4p4oqwuw7bak9-103248396421` | running | none | unless-stopped | High RAM pressure |
| data-core API | `api-dvq6dwsagsw4p4oqwuw7bak9-103248374709` | running | healthy | unless-stopped | Port 8000 internal |
| data-core worker | `worker-dvq6dwsagsw4p4oqwuw7bak9-103248433455` | running | none | unless-stopped | Port 8000 internal |
| poupi-crypto DB | `poupi-crypto-db-1` | running | healthy | unless-stopped | Public `5435` |
| Prometheus | `prometheus` | running | none | no | Public `9090` |
| Grafana | `grafana-q11p1efg13of6ujrfgu25lal` | running | healthy | unless-stopped | Port 3000 internal |
| Alertmanager | `alertmanager` | running | none | unless-stopped | Local `127.0.0.1:9093` |
| Shared Postgres | `multi_project_infra-postgres-1` | running | healthy | unless-stopped | Internal only |
| Shared Redis | `multi_project_infra-redis-1` | running | healthy | unless-stopped | Internal only |
| Coolify/Traefik | `coolify*`, `coolify-proxy` | running | healthy | always/unless-stopped | Platform control plane |

Legacy stopped stacks remain present and must not be deleted without backup and approval:

- `poupi-baby-backend-1`
- `poupi-baby-worker-1`
- `poupi-baby-postgres-1`
- `poupi-baby-redis-1`
- `poupi-jobs-api-1`
- `poupi-jobs-db-1`

## Target Architecture

### Server

- data-core API
- data-core scheduler
- data-core worker
- poupi-baby backend
- poupi-baby worker
- poupi-crypto API and related workers
- Redis/Postgres persistent services
- Prometheus
- Grafana
- Alertmanager
- Coolify/Traefik or equivalent deployment edge

### Local Notebook

- Frontend development
- Manual scripts
- Fast tests
- Debugging
- Replay/statistical analysis
- No always-on scheduler or worker
- No local production-like observability stack by default

## Port Policy

Public ports should be limited to reviewed HTTP/TLS entrypoints.

Required remediation before production-ready classification:

- Keep `80` and `443` public through Traefik/Coolify.
- Restrict Prometheus `9090` to private network, VPN, SSH tunnel, or authenticated reverse proxy.
- Restrict Postgres `5435` to private network, VPN, SSH tunnel, or remove public binding.
- Review Coolify exposed ports `8000`, `6001`, `6002`, and Traefik dashboard `8080`.
- Keep Alertmanager private unless protected by TLS and authentication.

## Volume Policy

All Docker volumes are KEEP unless an explicit backup, restore test, and approval exist.

Important persistent volumes observed:

- `multi_project_infra_postgres-data`
- `multi_project_infra_redis-data`
- `poupi-crypto_pgdata`
- `poupi_crypto_signal_dataset`
- `poupi-baby_postgres-data`
- `poupi-jobs_pgdata`
- `prometheus-data`
- `q11p1efg13of6ujrfgu25lal_grafana-data`
- `dvq6dwsagsw4p4oqwuw7bak9_runtime-data`
- `dvq6dwsagsw4p4oqwuw7bak9_runtime-logs`

## Readiness Gates

The server becomes READY only when all gates pass:

- Root disk under 75% or documented growth budget.
- Swap below 25% during normal load, or RAM upgraded.
- Backups exist for Postgres, Redis persistence, Grafana, Prometheus, runtime data, and datasets.
- Restore test completed for at least one recent backup.
- Prometheus and database ports are not public.
- All public services are behind TLS and reviewed routing.
- Healthchecks are explicit for API, scheduler heartbeat, worker heartbeat, Prometheus, Grafana, Alertmanager, Postgres, and Redis.
- No duplicate local schedulers/workers are running on the notebook.

## Current Decision

- Notebook DEV-only: GO.
- Server observability as existing internal runtime: DEGRADED.
- Server runtime as existing always-on runtime: DEGRADED.
- Adding more always-on load: NO-GO until capacity/security/backups are fixed.
- Live trading: NO-GO.
