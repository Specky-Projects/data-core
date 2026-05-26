# Scheduler thresholds

## Memoria

| Threshold | Severidade | Racional |
| --- | --- | --- |
| `> 0.60` | info | aviso preventivo para acompanhar crescimento sem ruido |
| `> 0.75 por 10m` | warning | pressao sustentada com tempo suficiente para filtrar burst |
| `> 0.90 por 3m` | critical | risco de OOM/restart com pouca margem |

## Swap

| Threshold | Severidade | Racional |
| --- | --- | --- |
| `> 0.20 por 10m` | warning | qualquer uso sustentado de swap no scheduler merece correlacao com host |

## Crescimento

`data_core_scheduler_growth_rate > 524288` por 15m com memoria acima de 60% sugere possivel leak. A regra nao declara leak definitivo: ela pede coleta de evidencias.

## OOM e restart

- `SCHEDULER_OOM_RECENT` e critical imediato.
- `increase(data_core_scheduler_restart_count[15m]) > 0` e critical porque restart inesperado pode interromper coleta.

## Backlog

`backlog_score > 0.75 por 10m` indica backlog suspeito. O score e normalizado e deve ser interpretado junto com `cycle_duration` e falhas recentes.

## Estado geral

`data_core_scheduler_state != 0 por 10m` evita ruido de transicoes curtas e captura degradacao sustentada.

