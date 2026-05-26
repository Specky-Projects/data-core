# Scheduler incident response

Este runbook e acionavel por alerta. As acoes sao deliberadamente manuais e reversiveis.

## Comandos base

```bash
curl -H "X-API-Key: $API_KEY" http://data-core-api:8000/api/v1/runtime/scheduler-summary | jq .
curl -H "X-API-Key: $API_KEY" http://data-core-api:8000/api/v1/runtime/scheduler-diagnosis | jq .
docker stats --no-stream scheduler-dvq6dwsagsw4p4oqwuw7bak9-103248396421
docker inspect scheduler-dvq6dwsagsw4p4oqwuw7bak9-103248396421 --format '{{.RestartCount}} {{.State.OOMKilled}} {{.HostConfig.Memory}} {{.HostConfig.MemorySwap}}'
docker logs scheduler-dvq6dwsagsw4p4oqwuw7bak9-103248396421 --since 30m --tail 300
journalctl -k --since "30 minutes ago" | grep -i -E 'oom|killed process'
```

## DataCoreSchedulerMemoryHigh

Diagnostico:
- Confirmar `memory_usage_ratio`, `growth_rate`, `trend` e `cycle_duration`.
- Verificar se o uso volta ao baseline apos o ciclo.
- Conferir `backlog_score`.

Acao:
- Nao reiniciar automaticamente.
- Observar pelo menos mais um ciclo se `trend=MEMORY_STABLE`.
- Se persistir e host tiver folga, planejar aumento controlado de memoria.

Rollback:
- Reverter apenas mudanca de limite se ela tiver causado regressao. Nao limpar volumes.

## DataCoreSchedulerMemoryCritical

Diagnostico:
- Preservar logs do scheduler e `docker inspect`.
- Verificar OOM recente e restart count.
- Confirmar se API/data-core seguem saudaveis.

Acao:
- Se memoria >90% continuar por varios minutos, preparar aumento de limite ou escala de host.
- Reinicio manual somente se o processo estiver travado, sem progresso de ciclos, e com evidencia preservada.

## DataCoreSchedulerSwapElevated

Diagnostico:
- Comparar swap do container com swap do host.
- Verificar se outros containers tambem estao pressionando memoria.

Acao:
- Se swap estiver estavel e memoria baixa, observar.
- Se swap crescer junto com memoria, tratar como possivel leak ou falta de RAM.

## DataCoreSchedulerOomRecent

Diagnostico:
- Confirmar `oom_recent=true`.
- Coletar `docker logs`, `docker inspect` e `journalctl`.
- Verificar se houve perda de coleta ou backlog.

Acao:
- Nao limpar Redis, filas ou volumes.
- Se repetir, aumentar memoria ou escalar host antes de alterar pipeline.

## DataCoreSchedulerRestartCountIncreasing

Diagnostico:
- Verificar `RestartCount`, `OOMKilled`, logs e eventos do host.
- Confirmar se o restart veio de deploy/recreate esperado ou crash.

Acao:
- Se foi deploy controlado, anotar e monitorar.
- Se foi crash, investigar OOM, excecao fatal ou healthcheck.

## DataCoreSchedulerPossibleMemoryLeak

Diagnostico:
- Verificar se `trend=POSSIBLE_MEMORY_LEAK` aparece por ciclos consecutivos.
- Comparar `growth_rate` com duracao do ciclo e backlog.

Acao:
- Coletar mais amostras antes de mexer em codigo.
- Investigar alocacoes se o crescimento nao recuar apos os ciclos.

## DataCoreSchedulerBacklogHigh

Diagnostico:
- Verificar pendentes de normalizacao.
- Conferir falhas de pipeline e duracao dos ciclos.

Acao:
- Nao aumentar concorrencia automaticamente.
- Investigar falhas e gargalos antes de qualquer ajuste operacional.

## DataCoreSchedulerStateNotHealthy

Diagnostico:
- Abrir `/api/v1/runtime/scheduler-diagnosis`.
- Usar `operational_state`, `explanation` e `recommended_action`.

Acao:
- Seguir o runbook especifico do estado retornado.

## Quando escalar host

Escalar quando houver swap alta no host, memoria critica repetida, OOM recorrente, ou pressao simultanea em mais de um container.

