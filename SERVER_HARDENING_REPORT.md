# Server Hardening Report

Date: 2026-05-25 / 2026-05-26 UTC

## Scope

Controlled hardening only:

- Reduce public exposure.
- Create recoverable backups.
- Validate restore without overwriting production.
- Preserve runtime behavior.

No strategy, thresholds, DRY_RUN, execution engine, sizing, risk logic, SL/TP, scraping, anti-bot, datasets, volumes, or production envs were changed.

## Evidence

Server evidence was saved on the server:

- Before snapshot: `/mnt/HC_Volume_105715453/poupi-hardening/evidence/before-20260525-205649.log`
- After snapshot: `/mnt/HC_Volume_105715453/poupi-hardening/evidence/after-20260525-210455.log`
- Backup root: `/mnt/HC_Volume_105715453/poupi-backups/20260525T205906Z`

## Changes Applied

### Public Exposure Guard

Installed a persistent systemd guard:

- Script: `/usr/local/sbin/poupi-docker-user-firewall.sh`
- Unit: `/etc/systemd/system/poupi-docker-user-firewall.service`
- State: enabled and active

Rules block public ingress on `eth0` for:

- Postgres crypto host port `5435`
- Prometheus host port `9090`

The rules are applied in both:

- `INPUT`, for host-level `docker-proxy` listeners
- `DOCKER-USER`, including conntrack original destination ports for Docker DNAT flows

SSH, HTTP, HTTPS, Coolify, and the public crypto API were not blocked.

### Log Rotation

Installed:

- `/etc/logrotate.d/poupi-docker-json-logs`

Policy:

- daily rotation
- 7 retained rotations
- compression
- `copytruncate`
- early rotation at 100 MB

No Docker daemon restart was performed.

## Before / After

| Item | Before | After |
| --- | --- | --- |
| Public Prometheus `9090` | Reachable before prior guard / public listener present | External test: unreachable |
| Public Postgres `5435` | Reachable | External test: unreachable |
| SSH `22` | Reachable | Reachable |
| HTTP `80` | Reachable | Reachable |
| HTTPS `443` | Reachable | Reachable |
| Crypto API `8002` | Reachable | Reachable |
| Prometheus local ready | 200 | 200 |
| Alertmanager local ready | 200 | 200 |
| Prometheus targets | 4/4 UP | 4/4 UP |
| Root disk | 82% used, 6.6 GiB free | 58% used, 15 GiB free |
| Extra volume | 9.3 GiB free | 9.2 GiB free |
| Swap | 639 MiB / 1 GiB | 916 MiB / 1 GiB |
| OOMKilled | none current | none current |

Note: no Docker prune was executed. Docker reported build cache as `0B` in the final `docker system df`; this appears to have been reclaimed/garbage-collected without a destructive prune command.

## Runtime Validation

Post-hardening:

- `poupi-crypto-api-1`: running, healthy, `/health` 200.
- `poupi-crypto-db-1`: running, healthy, `pg_isready` OK internally.
- `api-dvq6dwsagsw4p4oqwuw7bak9-103248374709`: running, healthy.
- `scheduler-dvq6dwsagsw4p4oqwuw7bak9-103248396421`: running, no Docker healthcheck.
- `worker-dvq6dwsagsw4p4oqwuw7bak9-103248433455`: running, no Docker healthcheck.
- `prometheus`: running, local `/-/ready` 200 and `/-/healthy` 200.
- `alertmanager`: running, local `/-/ready` 200 and `/-/healthy` 200.
- `grafana-q11p1efg13of6ujrfgu25lal`: running, healthy.

## Remaining Risks

- Swap remains critical at about 916 MiB of 1 GiB.
- `ufw` is not installed; protection is via iptables/nftables equivalent.
- Coolify/Traefik ports `8000`, `8080`, `6001`, and `6002` still need intentional review.
- Scheduler memory remains high, around 576 MiB of 768 MiB.
- Some running containers do not define Docker healthchecks.
- Coolify and Traefik mount Docker socket; this is expected for their role but classified as NEEDS_HARDENING.

## Decision

- Runtime server: DEGRADED, improved security.
- Observability: DEGRADED, improved exposure posture.
- Add new always-on load: NO-GO.
- Database migration: NO-GO until recurring backup policy is scheduled and restore runbook is approved.
- Production readiness: NO-GO.
- Paper trading: NO-GO pending explicit operational review.
- Live trading: ABSOLUTE NO-GO.
