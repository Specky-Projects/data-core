# Firewall And Exposure Audit

Date: 2026-05-25 / 2026-05-26 UTC

## Goal

Reduce critical public exposure without interrupting SSH, Coolify/Traefik, or required public APIs.

## Applied Control

Equivalent firewall control was implemented with iptables/nftables because Docker-published ports can bypass simple host firewall assumptions.

Installed:

- `/usr/local/sbin/poupi-docker-user-firewall.sh`
- `/etc/systemd/system/poupi-docker-user-firewall.service`

Service state:

- enabled
- active

## Protected Ports

| Port | Service | Before | After |
| --- | --- | --- | --- |
| `9090` | Prometheus | Public listener present | External TCP unreachable |
| `5435` | poupi-crypto Postgres | External TCP reachable | External TCP unreachable |

Internal validation:

- Prometheus local `/-/ready`: 200.
- Prometheus local `/-/healthy`: 200.
- Prometheus targets: 4/4 UP.
- `poupi-crypto-db-1` internal `pg_isready`: OK.

## Public Ports Still Reachable

| Port | Purpose | Status |
| --- | --- | --- |
| `22` | SSH | Reachable |
| `80` | HTTP via Traefik/Coolify | Reachable |
| `443` | HTTPS via Traefik/Coolify | Reachable |
| `8002` | poupi-crypto API | Reachable |

Ports requiring review:

- `8000` Coolify public binding.
- `8080` Traefik dashboard/proxy binding.
- `6001-6002` Coolify realtime.

## Security Classification

| Item | Classification | Notes |
| --- | --- | --- |
| Prometheus public exposure | SAFE after guard | Still bound by docker-proxy, blocked externally |
| Postgres public exposure | SAFE after guard | Still bound by docker-proxy, blocked externally |
| Redis public exposure | SAFE | No public Redis listener found |
| Docker socket mounts | NEEDS_HARDENING | Present in Coolify/Traefik operational containers |
| Privileged containers | SAFE | No running privileged containers found |
| Root containers | NEEDS_HARDENING | Some infra containers run as default/root user |
| Grafana auth | NEEDS_HARDENING | Container healthy; auth path not fully audited here |
| UFW | NEEDS_HARDENING | Not installed; iptables/nftables guard used instead |

## Rollback

To roll back only the exposure guard:

1. Disable the service:
   `systemctl disable --now poupi-docker-user-firewall.service`
2. Remove matching `INPUT` and `DOCKER-USER` rules for `5435` and `9090`.
3. Re-test SSH, `80`, `443`, `8002`, Prometheus local readiness, and Postgres internal readiness.

Rollback should only be used if the guard unexpectedly breaks a required path. Current validation shows it does not.

## Decision

Exposure posture: improved.

Server security: DEGRADED but no longer critically exposing Prometheus and Postgres to the public internet.
