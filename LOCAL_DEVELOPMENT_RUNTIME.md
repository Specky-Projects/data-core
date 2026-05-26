# Local Development Runtime

This notebook must be treated as a development and debugging workstation, not as
an always-on Poupi runtime.

## Local scope

Use the notebook for:

- frontend development
- manual scripts
- fast tests
- debugging
- replay and statistical analysis
- short-lived local API sessions

Do not use the notebook as an always-on runtime for:

- schedulers
- workers
- production-like APIs
- Prometheus, Grafana, or Alertmanager
- persistent Redis/Postgres workloads

## Local Docker rule

Use the local override file whenever Docker is needed:

```powershell
docker compose -f docker-compose.yml -f docker-compose.local.yml --profile dev up
```

The local override sets `restart: "no"` and attaches services to profiles so
Docker Desktop can open without automatically bringing the full platform online.

## Common commands

Data-core API with local dependencies:

```powershell
cd C:\Users\dev\Documents\Projetos\data-core
docker compose -f docker-compose.yml -f docker-compose.local.yml --profile dev up api
```

Data-core full runtime, manually:

```powershell
cd C:\Users\dev\Documents\Projetos\data-core
docker compose -f docker-compose.yml -f docker-compose.local.yml --profile runtime up
```

Data-core observability only:

```powershell
cd C:\Users\dev\Documents\Projetos\data-core
docker compose -f docker-compose.yml -f docker-compose.local.yml --profile observability up
```

Poupi Baby backend with local Redis:

```powershell
cd C:\Users\dev\Documents\Projetos\poupi-baby
docker compose -f docker-compose.yml -f docker-compose.local.yml --profile dev up backend
```

Poupi Crypto API with DRY_RUN inherited from the base compose:

```powershell
cd C:\Users\dev\Documents\Projetos\poupi-crypto
docker compose -f docker-compose.yml -f docker-compose.local.yml --profile dev up api
```

Frontend without Docker:

```powershell
cd C:\Users\dev\Documents\Projetos\poupi-frontend
pnpm dev
```

## Stop commands

Stop a local stack without removing volumes:

```powershell
docker compose -f docker-compose.yml -f docker-compose.local.yml down
```

Do not use:

```powershell
docker system prune -a
docker volume prune
docker system prune --volumes
```

