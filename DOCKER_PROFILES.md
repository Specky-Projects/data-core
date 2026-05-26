# Docker Profiles

Poupi local Docker usage is profile-driven. Production compose files remain
unchanged; local behavior comes from `docker-compose.local.yml`.

## Profiles

| Profile | Purpose | Typical services |
| --- | --- | --- |
| `dev` | Short-lived local development | API plus minimum dependencies |
| `frontend` | Reserved for frontend conventions | Frontend normally runs outside Docker |
| `runtime` | Manual full local runtime | API, DB, Redis, scheduler, worker |
| `scheduler` | Scheduler-only debugging | Scheduler plus dependencies |
| `worker` | Worker-only debugging | Worker plus dependencies |
| `observability` | Local dashboards and alerts | Prometheus, Grafana, Alertmanager |
| `debug` | Tests and diagnostics | Tests, APIs, support dependencies |

## Repository overrides

Created local overrides:

- `data-core/docker-compose.local.yml`
- `poupi-baby/docker-compose.local.yml`
- `poupi-crypto/docker-compose.local.yml`
- `poupi-frontend/docker-compose.local.yml`

Each local override sets `restart: "no"`. Services only run when a matching
profile is explicitly requested.

## Current restart issue

Existing local containers were created with `restart: unless-stopped`. Updating
compose files alone does not change already-created containers. For the current
notebook, update local container restart policy once:

```powershell
docker update --restart=no data-core-api-1 data-core-scheduler-1 data-core-worker-1 data-core-postgres-1 data-core-redis-1 data-core-grafana-1 data-core-prometheus-1 data-core-alertmanager-1 poupi-baby-backend-1 poupi-baby-worker-1 poupi-baby-redis-1
```

This does not remove containers, volumes, databases, images, or datasets.

## Recreate with local policy

When a stack must be rebuilt locally, use the local override:

```powershell
docker compose -f docker-compose.yml -f docker-compose.local.yml --profile dev up --build
```

Avoid running plain `docker compose up` on the notebook for Poupi stacks.

