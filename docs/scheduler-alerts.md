# Scheduler alerts

Esta pagina descreve os alertas preventivos do scheduler do data-core. Todos os alertas sao observacionais: nenhum deles reinicia container, altera concorrencia ou modifica pipeline.

## Severidades

| Severidade | Uso |
| --- | --- |
| `info` | Estado preventivo sem acao imediata. Exemplo: memoria acima de 60%, mas estavel. |
| `warning` | Pressao sustentada ou sinal de degradacao. Exige observacao e diagnostico. |
| `critical` | Risco de OOM/restart ou evento recente. Exige coleta de evidencias antes de qualquer acao. |

## Regras Prometheus

| Alerta | Expressao | Janela | Severidade |
| --- | --- | --- | --- |
| `DataCoreSchedulerMemoryHigh` | `data_core_scheduler_memory_usage_ratio > 0.75` | 10m | warning |
| `DataCoreSchedulerMemoryCritical` | `data_core_scheduler_memory_usage_ratio > 0.90` | 3m | critical |
| `DataCoreSchedulerSwapElevated` | `data_core_scheduler_swap_usage_ratio > 0.20` | 10m | warning |
| `DataCoreSchedulerOomRecent` | `data_core_scheduler_state == 4` | imediato | critical |
| `DataCoreSchedulerRestartCountIncreasing` | `increase(data_core_scheduler_restart_count[15m]) > 0` | imediato | critical |
| `DataCoreSchedulerPossibleMemoryLeak` | `data_core_scheduler_growth_rate > 524288 and data_core_scheduler_memory_usage_ratio > 0.60` | 15m | warning |
| `DataCoreSchedulerBacklogHigh` | `data_core_scheduler_backlog_score > 0.75` | 10m | warning |
| `DataCoreSchedulerStateNotHealthy` | `data_core_scheduler_state != 0` | 10m | warning |

## Estados numericos

| Valor | Estado |
| --- | --- |
| 0 | `SCHEDULER_HEALTHY` |
| 1 | `SCHEDULER_MEMORY_ELEVATED` |
| 2 | `SCHEDULER_MEMORY_HIGH` |
| 3 | `SCHEDULER_MEMORY_CRITICAL` |
| 4 | `SCHEDULER_OOM_RECENT` |
| 5 | `SCHEDULER_RESTART_LOOP` |
| 6 | `SCHEDULER_DEGRADED` |
| 7 | `OBSERVE_MORE` |

## Payload Telegram

O endpoint `/api/v1/runtime/scheduler-alert-payload` gera o payload atual sem enviar mensagem. Use para validar sem produzir ruido operacional.

