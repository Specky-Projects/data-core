# Data-core scheduler watchdog

O `DataCoreSchedulerWatchdog` monitora preventivamente o container do scheduler do data-core sem alterar coleta, normalizacao, analytics, providers ou concorrencia.

## Arquitetura

- O processo `app.jobs.scheduler_runner` inicia um probe daemon.
- O probe le apenas cgroup local em `/sys/fs/cgroup`.
- O snapshot e escrito em `/app/runtime-data/scheduler_watchdog_snapshot.json`.
- A API le o snapshot pelo volume compartilhado e expoe `GET /api/v1/runtime/scheduler-diagnosis`.
- As metricas Prometheus sao atualizadas quando o endpoint e chamado.

Essa abordagem evita montar `/var/run/docker.sock` no container da API.

## Estados

| Estado | Severidade | Quando ocorre |
| --- | --- | --- |
| `SCHEDULER_HEALTHY` | info | memoria, swap, OOM e backlog dentro do esperado |
| `SCHEDULER_MEMORY_ELEVATED` | info | memoria acima de 60% |
| `SCHEDULER_MEMORY_HIGH` | warning | memoria acima de 75% ou swap acima de 70% |
| `SCHEDULER_MEMORY_CRITICAL` | critical | memoria acima de 90% |
| `SCHEDULER_OOM_RECENT` | critical | novo `oom_kill` detectado no cgroup |
| `SCHEDULER_RESTART_LOOP` | critical | tres ou mais reinicios observados pelo probe |
| `SCHEDULER_DEGRADED` | warning | snapshot stale, ciclos lentos ou backlog alto |
| `OBSERVE_MORE` | warning | tendencia sugere possivel leak, ainda sem pressao critica |

## Tendencia de memoria

| Tendencia | Interpretacao |
| --- | --- |
| `MEMORY_STABLE` | memoria estabilizada ou oscilando pouco |
| `MEMORY_GROWING` | crescimento moderado |
| `MEMORY_SPIKING` | pico temporario com recuo |
| `POSSIBLE_MEMORY_LEAK` | crescimento continuo em amostras recentes |

## Endpoint

```bash
curl -H "X-API-Key: $API_KEY" http://data-core-api:8000/api/v1/runtime/scheduler-diagnosis
```

Campos principais: `memory_usage_ratio`, `swap_usage_ratio`, `restart_count`, `oom_recent`, `growth_rate`, `trend_state`, `operational_state`, `alert_severity`, `cycle_duration`, `backlog_score`, `explanation` e `recommended_action`.

## Metricas

- `data_core_scheduler_memory_usage_bytes`
- `data_core_scheduler_memory_limit_bytes`
- `data_core_scheduler_memory_usage_ratio`
- `data_core_scheduler_swap_usage_ratio`
- `data_core_scheduler_restart_count`
- `data_core_scheduler_oom_events_total`
- `data_core_scheduler_state`
- `data_core_scheduler_alert_severity`
- `data_core_scheduler_growth_rate`
- `data_core_scheduler_cycle_duration_seconds`
- `data_core_scheduler_backlog_score`
