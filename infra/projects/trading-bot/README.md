# Trading Bot

Projeto operacional do bot de trading.

## Padrao

- deploy independente no Coolify;
- sem porta publica por padrao;
- rede propria `trading_bot_app`;
- rede compartilhada `infra_internal`;
- Data Core interno em `http://data-core-api:8000`;
- Postgres reservado em `trading_bot_db`;
- Redis sugerido em DB `3`;
- modo inicial sempre `PAPER_TRADING=true`.

Banco:

```text
trading_bot_db
trading_bot_user
```

## Servicos

- `bot-runner`: processo principal, executa `python -m workers.crypto_coin_worker`;
- `autotune`: ferramenta opcional via profile `tools`, executada sob demanda em `--dry-run` por padrao.

## Storage atual

O dominio `crypto_coin` ainda nao tem adapter PostgreSQL implementado para o storage do bot. Por isso, o runner usa:

```text
sqlite:////app/runtime-data/crypto_coin_bot.sqlite3
```

Esse SQLite fica em volume Docker persistente. O `trading_bot_db` fica reservado para migrar estado/sinais/ordens quando o adapter Postgres for implementado.

## Fluxo recomendado

```text
data-core coleta/normaliza mercado
trading-bot consome Data Core quando o adapter estiver conectado
trading-bot registra decisoes/posicoes em storage proprio
```

Enquanto o adapter de feed interno nao estiver pronto, o runner legado ainda pode buscar dados publicos via exchange em modo paper.

## Auto-tuner

Em producao, `AUTOTUNE_ENABLED=false` por padrao. Isso evita que o bot tente alterar `.env` dentro de um container gerenciado pelo Coolify.

Para avaliar parametros sem aplicar automaticamente:

```bash
docker compose --env-file .env -f docker-compose.prod.yml --profile tools run --rm autotune
```

Promova parametros manualmente depois de revisar o resultado.
