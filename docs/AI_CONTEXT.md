# AI Context

Este repositorio e um backend modular de data platform. O frontend deve ser um projeto separado e consumir apenas a API.

## Onde mexer

- `api/`: contratos HTTP FastAPI.
- `collectors/`: coleta de dados por dominio. Cada collector herda de `BaseCollector`.
- `workers/`: execucao operacional reutilizavel. Use workers para jobs long-running ou tarefas que nao devem viver dentro do request HTTP.
- `scheduler/`: agenda collectors/jobs com APScheduler.
- `database/`: modelos e sessao SQLAlchemy do Data Core.
- `domains/crypto_coin/`: backend migrado do bot crypto-coin, isolado como dominio.

## Padrao recomendado

1. Coloque integracoes externas e regras especificas dentro do dominio.
2. Exponha uma adaptacao pequena em `collectors/` ou `workers/`.
3. Registre collectors em `collectors/registry.py`.
4. Exponha endpoints em `api/` apenas quando houver contrato claro para frontend/SaaS.
5. Mantenha migracoes em `alembic/versions`.

## Crypto Coin

O dominio `domains/crypto_coin` contem trading engine, exchange connector, indicadores, backtesting, autotune e analytics migrados do projeto original.

Use `collectors/crypto/crypto_coin_ohlcv.py` como exemplo de adaptador limpo: ele chama o conector do dominio e devolve `CollectedItem` para o Data Core persistir historico de coleta.

Documentacao original migrada:

- `docs/crypto_coin/context`
- `docs/crypto_coin/systems`
- `docs/crypto_coin/CLAUDE.original.md`

## Poupi Baby

O dominio `domains/poupi_baby` contem a interface backend migrada do projeto Poupi.

- `domains/poupi_baby/backend`: backend NestJS original.
- `domains/poupi_baby/worker`: worker BullMQ original.
- `domains/poupi_baby/interface.py`: manifest Python com modulos e endpoints.

Endpoints de introspeccao no Data Core:

- `GET /api/v1/poupi-baby`
- `GET /api/v1/poupi-baby/modules`
- `GET /api/v1/poupi-baby/endpoints`

Documentacao original migrada:

- `docs/poupi_baby/context`
- `docs/poupi_baby/backend`
- `docs/poupi_baby/worker`
- `docs/poupi_baby/queues`
- `docs/poupi_baby/analytics`
