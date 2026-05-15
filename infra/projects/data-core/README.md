# Data Core

Deploy recomendado no Coolify:

- app API com dominio publico protegido por API key;
- scheduler como service sem porta publica;
- worker como service sem porta publica;
- banco `data_core_db`;
- Redis DB `2`.
- rede interna compartilhada `infra_internal`;
- alias interno `data-core-api`.

O compose usa o Dockerfile real do repositorio raiz (`../../..`) e separa API, scheduler e worker em containers diferentes.
Somente a API executa `alembic upgrade head`; scheduler e worker aguardam a API ficar saudavel para evitar corrida de migrations.

Comando de deploy da API:

```bash
alembic upgrade head && uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000
```

Endpoints importantes:

- `/health`
- `/metrics` se monitoramento estiver habilitado;
- `/api/v1/poupi-baby/price-feed`
- `/api/v1/crypto/candles-feed`
- `/api/v1/crypto/signals-feed`

Scheduler e worker nao precisam de porta publica.
