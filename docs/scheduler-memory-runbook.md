# Scheduler memory runbook

## Diagnostico rapido

```bash
curl -H "X-API-Key: $API_KEY" http://data-core-api:8000/api/v1/runtime/scheduler-diagnosis | jq .
docker stats --no-stream scheduler-dvq6dwsagsw4p4oqwuw7bak9-103248396421
docker inspect scheduler-dvq6dwsagsw4p4oqwuw7bak9-103248396421 --format '{{.RestartCount}} {{.State.OOMKilled}}'
journalctl -k --since "2 hours ago" | grep -i -E 'oom|killed process'
```

## Thresholds

- Info: memoria acima de 60%.
- Warning: memoria acima de 75% ou swap acima de 70%.
- Critical: memoria acima de 90%, OOM recente ou loop de restart.

## Acoes seguras

- Confirmar se `memory_usage_ratio` esta estabilizado.
- Comparar `growth_rate` e `trend_state` por alguns ciclos.
- Conferir logs recentes do scheduler.
- Aumentar limite de memoria apenas se a pressao for sustentada.
- Escalar host se memoria disponivel e swap continuarem degradando.

## Acoes perigosas

- Nao limpar volumes.
- Nao executar `docker system prune` agressivo.
- Nao reduzir concorrencia sem evidencia de que o scheduler esta saturando pipeline.
- Nao alterar providers ou logica de coleta para resolver alerta de memoria.

## Quando reiniciar

Reiniciar somente se houver loop travado, memoria critica persistente e evidencia de que o processo nao esta completando ciclos. Antes disso, coletar snapshot, logs e `docker inspect`.

## Rollback

O watchdog e observacional. Para rollback do probe, remover a chamada `start_scheduler_watchdog_probe()` do runner e manter o endpoint retornando snapshot indisponivel. Isso nao altera pipeline de dados.

