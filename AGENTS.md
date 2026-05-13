# Data Core Agent Guide

Este repositorio e backend-only. Nao crie frontend aqui.

## Arquitetura

- `api/`: endpoints FastAPI.
- `collectors/`: adaptadores de coleta. Todo collector deve herdar de `collectors.base.BaseCollector`.
- `workers/`: execucao operacional e jobs long-running.
- `scheduler/`: agenda de collectors e workers.
- `database/`: modelos SQLAlchemy e sessao do Data Core.
- `domains/`: logica de dominio isolada.
- `domains/crypto_coin/`: backend migrado do `bot-crypto-coin`.
- `domains/poupi_baby/`: interface backend migrada do `poupi`.

## Regras

- Codigo novo de dominio deve ficar em `domains/<domain>`.
- API e scheduler devem chamar dominios por adaptadores pequenos em `collectors/` ou `workers/`.
- Nao versionar `.env`, bancos locais, logs ou artefatos de runtime.
- Preferir PostgreSQL para dados do Data Core. O SQLite em `domains/crypto_coin/data/storage` e legado/compatibilidade.
- A pasta `domains/crypto_coin/legacy` e ponte temporaria para scripts antigos; nao coloque codigo novo nela.
- O backend TypeScript em `domains/poupi_baby/backend` e contrato/referencia. Integre pelo Data Core com adaptadores Python pequenos.
- Quando adicionar collector, registre em `collectors/registry.py`.
- Quando mudar schema do Data Core, crie migracao em `alembic/versions`.

## Contexto

Leia `docs/AI_CONTEXT.md` antes de mudancas grandes.
