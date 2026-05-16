# data-core — Agent Guide

Este repositorio e backend-only. Nao crie frontend aqui.

> Contexto operacional completo: `ai/CONTEXT.md`
> Regras de sincronizacao de docs: `ai/DOC_SYNC_RULES.md`

---

## Estrutura de diretorios

| Diretorio | Proposito |
|---|---|
| `api/` | Endpoints FastAPI, schemas, dependencias HTTP |
| `app/main.py` | App factory, lifespan, middleware, `/health`, `/live`, `/ready` |
| `app/middleware/` | `CorrelationMiddleware` — X-Correlation-ID + X-Trace-ID por request |
| `app/pipeline/` | `PipelineRun`, `PipelineFailure` models + `PipelineRecorder` context manager |
| `app/modules/<domain>/` | Normalizadores e processors por dominio |
| `collectors/` | Adaptadores de coleta. Todo collector herda de `BaseCollector` |
| `workers/` | `collector_worker.py` — executa collectors, salva raw, atualiza status |
| `scheduler/` | APScheduler: `jobs.py`, `circuit_breaker.py`, `retry.py` |
| `database/` | SQLAlchemy engine, sessao, modelos do Data Core |
| `logs/` | `config.py`: `CorrelationFilter`, `PipelineFilter`, `set_pipeline_context()` |
| `api/metrics.py` | Todos os Prometheus metrics + `measure_pipeline_stage()` |
| `alembic/versions/` | Migracoes. Head atual: `0015_pipeline_observability` |
| `docs/` | Documentacao humana (DATA_FLOW, API_ENDPOINTS, etc.) |
| `ai/` | Contexto para agentes IA (CONTEXT, RUNBOOK, DOC_SYNC_RULES) |

---

## Regras de codigo

### Collectors
- Todo collector herda de `collectors/base.py::BaseCollector`
- Implemente `async def collect(self) -> list[CollectedItem]`
- Registre em `collectors/registry.py`
- Adicione job em `scheduler/jobs.py`

### Pipeline jobs
- Todo job de normalizacao e analytics deve ser wrapped com `PipelineRecorder`
- Exemplo em `scheduler/jobs.py::normalize_job` e `analytics_job`
- `PipelineRecorder` insere em `pipeline_runs`, registra falhas em `pipeline_failures`

### Migracoes
- Revision ID <= 32 chars (constraint `alembic_version varchar(32)`)
- Nomear: `0016_short_description` (sempre prefixar com numero)
- `down_revision = "0015_pipeline_observability"` (head atual)

### Metrics
- Todos os metrics definidos em `api/metrics.py` — nunca definir em outro lugar
- Usar `measure_pipeline_stage(domain, stage)` como context manager nos jobs
- Incrementar `collection_raw_saved_total` no `workers/collector_worker.py` apos salvar

### Logging
- Usar `set_pipeline_context(domain, stage)` antes de operacoes de pipeline
- `clear_pipeline_context()` no finally
- Ja implementado via `PipelineRecorder` — nao duplicar em novos jobs

### Modelos
- Modelos de dominio em `database/models.py` ou `app/modules/<domain>/models.py`
- Modelos de observabilidade em `app/pipeline/models.py`
- Sempre adicionar migracao ao criar/alterar modelos

---

## Regra de sincronizacao de documentacao (OBRIGATORIA)

Toda mudanca relevante deve atualizar automaticamente, sem esperar instrucao:

1. `/docs/*.md` relevante
2. `ai/CONTEXT.md` (se arquitetura, topologia ou gaps mudaram)
3. `README.md` (se setup, endpoints ou roles mudaram)
4. `AGENTS.md` (se regras mudaram)

Ver detalhes: `ai/DOC_SYNC_RULES.md`

---

## Dominios

| Dominio | Status | Collector ativo | Analytics |
|---|---|---|---|
| `crypto` | Operacional | `crypto.crypto_coin_ohlcv` (15min) | RSI, MA, ATR, ADX, signal, confidence, regime |
| `ecommerce` | Demo | `ecommerce.generic_product` | avg/z-score (CLV stub) |
| `real_estate` | Demo | `real_estate.generic_listing` | price/m2 (neighborhood_avg stub) |
| `sports_betting` | Demo | `sports_betting.generic_odds` | line_movement (CLV/EV stub) |

---

## Constraints de arquitetura

- Nao versionar `.env`, bancos locais, logs ou artefatos de runtime
- Preferir PostgreSQL para dados do Data Core
- `domains/crypto_coin/data/storage` e SQLite legado — nao expandir
- `domains/poupi_baby/backend` e backend NestJS de referencia — nao modificar
- `domains/crypto_coin/legacy` e ponte temporaria — nao adicionar codigo novo

---

## Contexto de producao

- Servidor: Hetzner, gerenciado por Coolify
- DB: `data_core_db` em `multi_project_infra-postgres-1`
- Redis: compartilhado com prefixo por projeto
- API alias na rede Docker: `data-core-api` (rede `coolify` e `infra_internal`)
- Deploy: push para `main` → Coolify rebuilda automaticamente
- Migracao: roda automaticamente no startup do container `api`
