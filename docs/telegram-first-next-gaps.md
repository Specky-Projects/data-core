# Telegram-First Observability Gaps

Data: 2026-05-26

Este arquivo lista gaps encontrados ao preparar os alertas `[SHADOW]` para o Poupi System Bot.

## Gaps Encontrados

### Postgres Down

Nao foi encontrado scrape Prometheus dedicado para Postgres no `prometheus.yml`.

Opcoes:

- Adicionar `postgres_exporter`.
- Expor uma metrica de dependencia pela API, por exemplo `data_core_dependency_up{dependency="postgres"}`.
- Criar alerta a partir de health/readiness se a metrica ja existir em outro ambiente.

### Redis Down Global

Nao foi encontrado scrape Prometheus dedicado para Redis global no `prometheus.yml`.

Existe `redis_up{job="poupi-crypto-volatile"}` para o runtime volatile, mas nao um Redis global/data-core.

Opcoes:

- Adicionar `redis_exporter`.
- Expor `data_core_dependency_up{dependency="redis"}` pela API.
- Alertar somente quando `CACHE_ENABLED=true` ou quando Redis for dependencia de runtime.

### Container Restart Loop Generico

Existem metricas especificas do scheduler:

- `data_core_scheduler_restart_count`
- `scheduler_restart_loop_total`

Nao foi confirmada uma metrica generica por container para todos os runtimes.

Opcoes:

- Adicionar cAdvisor/node exporter se ainda nao existir no ambiente servidor.
- Expor restart count por runtime no proprio endpoint `/metrics`.

### Backup Status

Nao foi encontrada metrica Prometheus de ultimo backup bem-sucedido.

Metrica recomendada:

- `poupi_backup_last_success_timestamp_seconds{target="postgres"}`
- `poupi_backup_restore_verified{target="postgres"}`

### Daily Executive Summary

Ainda falta job periodico consultando Prometheus e enviando resumo via Poupi System Bot.

Primeira versao recomendada:

- data-core API up
- scheduler heartbeat
- scheduler restarts/OOM
- normalization lag
- queue lag
- volatile runtime OOM
- volatile Redis
- alertas ativos critical/warning
