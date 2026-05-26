# Local Minimal Setup

The notebook is a development and operations client only. It should not run continuous production workloads.

Last verified: 2026-05-26.

Current local runtime status: no Docker containers are running after reversible `docker compose stop` / `docker stop` operations. No volumes, images, databases, or local files were deleted.

Local secret inventory still shows real `.env` / `.env.local` files in local project folders. Treat them as temporary until a vault or encrypted archive is chosen.

## Required Locally

- Git
- Code editor
- SSH client
- Access to GitHub
- Optional: Docker Desktop for isolated tests only
- Optional: Node/Python tooling for project-specific development only

## Not Required Locally For Continuous Runtime

- PostgreSQL
- Redis
- schedulers
- workers
- scrapers
- Prometheus
- Grafana
- Alertmanager
- production data volumes
- production `.env` files

## Local Secret Policy

Do not keep production secrets on the notebook unless actively needed for a short, documented operation.

Allowed locally:

- `.env.example`
- `.env.local.example`
- SSH config without embedded passwords
- API placeholders

To retire local secrets:

```powershell
# Confirm server-side envs exist before doing this.
Move-Item .env .env.local.backup.DO_NOT_COMMIT
```

Never commit:

```text
.env
.env.*
!.env.example
!.env.local.example
```

## Recommended Local Workflow

```text
edit locally -> run focused tests if needed -> commit -> push -> remote deploy/CI -> remote health check
```

## Remote Operation Commands

From a local clone:

```bash
scripts/remote-health.sh
scripts/remote-logs.sh data-core api
scripts/remote-deploy.sh poupi-crypto
scripts/remote-backup.sh inventory
```

## Local Cleanup Checklist

- Real `.env` files replaced with examples or encrypted vault workflow.
- Docker Desktop not required for daily operation.
- No local scheduler process configured at login/startup.
- No local Postgres/Redis services running continuously.
- Frontend `.env.local` files contain non-secret remote URLs only.

## Local Secret Inventory

Real local env files found on 2026-05-26:

```text
C:\Users\dev\Documents\Projetos\data-core\.env
C:\Users\dev\Documents\Projetos\poupi-baby\.env
C:\Users\dev\Documents\Projetos\poupi-baby\backend\.env
C:\Users\dev\Documents\Projetos\poupi-crypto\.env
C:\Users\dev\Documents\Projetos\poupi-crypto\.env.volatile
C:\Users\dev\Documents\Projetos\poupi-frontend\apps\crypto-dashboard\.env.local
C:\Users\dev\Documents\Projetos\poupi-frontend\apps\poupi-baby\.env.local
C:\Users\dev\Documents\Projetos\poupi-frontend\apps\quant-dashboard\.env.local
C:\Users\dev\Documents\Projetos\poupi-frontend\apps\real-estate-dashboard\.env.local
C:\Users\dev\Documents\Projetos\poupi-frontend\apps\sports-dashboard\.env.local
```

Do not delete these blindly. Quarantine or vault them only after confirming the matching remote env keys exist and the owner has a recovery path.

## Verified Cleanup Commands

These commands were used to stop local continuous runtime without deleting data:

```powershell
cd C:\Users\dev\Documents\Projetos\data-core
docker compose stop

cd C:\Users\dev\Documents\Projetos\poupi-baby
docker compose stop

docker stop data-core-prometheus-1 data-core-alertmanager-1 data-core-grafana-1
docker ps
```

Expected final state:

```text
NAMES     IMAGE     PORTS     STATUS
```
