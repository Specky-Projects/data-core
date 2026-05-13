# Data Core

Backend modular para coleta de dados, agendamento, armazenamento, logs, retries e API REST.

Este projeto fica separado do frontend. O frontend deve consumir apenas a API HTTP exposta pelo Data Core e deve ter deploy independente.

## Arquitetura

```text
data-core/
  app/
    main.py          # ponto de entrada FastAPI
  api/               # FastAPI routers, schemas e dependencias HTTP
  collectors/        # collectors por dominio e registry
    real_estate/
    ecommerce/
    crypto/
    sports_betting/
  database/          # SQLAlchemy engine, session e modelos
  logs/              # configuracao de logging
  scheduler/         # APScheduler e jobs
  utils/             # retry, hashing e helpers
  workers/           # execucao reutilizavel de collectors
  alembic/           # migracoes futuras
  docker-compose.yml
  Dockerfile
```

## Rodando localmente

```bash
cp .env.example .env
docker compose up --build
```

O container aplica `alembic upgrade head` antes de iniciar a API.

API:

- `GET /health`
- `GET /api/v1/collectors`
- `POST /api/v1/collectors/{collector_name}/run`
- `GET /api/v1/runs`
- `GET /api/v1/records`

## Adicionando um collector

1. Crie um arquivo em `app/collectors/<dominio>/<site>.py`.
2. Herde de `BaseCollector`.
3. Implemente `collect`.
4. Registre o collector em `app/collectors/registry.py`.

O collector retorna `CollectedItem` com `external_id`, `source_url`, `payload` e metadados. O worker salva histórico de execução, registros coletados e falhas.

## Separacao frontend/backend

- Frontend: Next.js/React separado, sem scraping, deploy independente.
- Backend/Data Core: collectors, scheduler, banco, logs, retries, API e analytics futuros.
