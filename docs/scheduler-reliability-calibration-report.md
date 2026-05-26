# Scheduler Reliability Calibration Report

Data: 2026-05-23

## Escopo

Calibracao segura do Scheduler Reliability System em dry-run. Nenhuma protecao efetiva foi ativada, nenhum restart automatico foi configurado, nenhuma concorrencia real foi reduzida e scraping/trading/providers permanecem fora do escopo.

## Fonte analisada

Arquivo esperado: `runtime-data/scheduler_reliability_audit.jsonl`

Resultado local: arquivo ausente no momento da calibracao. O diretorio `runtime-data/` existe e o `docker-compose.yml` monta `./runtime-data:/app/runtime-data` tanto no servico `api` quanto no `scheduler`, portanto o caminho e persistente quando os servicos rodam pelo compose. A ausencia indica que nenhum ciclo runtime observado executou uma decisao wrapped de `SchedulerReliabilityEngine.decide()` desde a fase anterior.

## Resumo operacional

| Item | Resultado |
| --- | --- |
| Modo predominante | `UNKNOWN` sem eventos |
| Maior pressao observada | `0.0` sem eventos |
| Maior memoria observada | `0.0` sem eventos |
| Maior backlog observado | `0` sem eventos |
| Falsos positivos | nao avaliavel sem eventos |
| Oscilacao | nao avaliavel sem eventos |
| Recomendacao automatica | `KEEP_DRY_RUN_INSUFFICIENT_DATA` |

## Recomendacao

Manter dry-run.

Nao ativar `SCHEDULER_RELIABILITY_ENABLED` ainda e manter `SCHEDULER_RELIABILITY_DRY_RUN=true` ate existir uma janela real de eventos suficiente para validar estabilidade de `NORMAL`, mudancas de modo, growth rates, backlog growth rate, schema e falsos positivos.

## Smoke operacional

Comando read-only:

```bash
python scripts/scheduler_reliability_smoke.py --base-url http://data-core-api:8000
```

O smoke valida:

- existencia e tamanho de `runtime-data/scheduler_reliability_audit.jsonl`;
- integridade JSONL e schema por linha;
- endpoint `/api/v1/runtime/scheduler-reliability-audit`, se `--base-url` for informado;
- metricas Prometheus em `/metrics`, se `--base-url` for informado;
- paineis obrigatorios no dashboard Grafana.

Ele nao altera env, nao reinicia containers, nao mata processos, nao habilita reliability e nao chama `/scheduler-protection`.

## Proximo gate

Reavaliar quando `/api/v1/runtime/scheduler-reliability-audit` retornar:

- `window_hours >= 6`.
- `total_events >= 24`.
- `normal_stable=true`.
- `corrupt_lines=0` e `schema_errors=0`.
- `false_positive_ratio <= 0.02`.
- `mode_changes_total / total_events <= 0.10`.
- ausencia de `PROTECTIVE` ou `CRITICAL_PROTECTION` sustentado.
- recomendacao `READY_FOR_LIMITED_ENABLEMENT` antes de qualquer ativacao parcial.

## Validacao de deploy/runtime

Data: 2026-05-24

### Runtime validado

| Item | Evidencia |
| --- | --- |
| Container API | `data-core-api-1` |
| Imagem API | `data-core-api-light:latest` |
| Image ID apos rebuild | `f468b51bb7fc` |
| Git local | `79d4e43` |
| Status | API healthy em `localhost:8000` |
| Scheduler service | nao iniciado no compose ativo; disponivel apenas via profile `full-stack` |

Atualizacao feita de forma restrita com build/recreate somente do servico `api`, preservando volumes e dependencias. Nenhum servico `scheduler`, `worker`, `postgres`, `redis`, `prometheus` ou `grafana` foi recriado nesta validacao.

### Env efetivo

| Variavel | Valor observado |
| --- | --- |
| `SCHEDULER_RELIABILITY_ENABLED` | `false` |
| `SCHEDULER_RELIABILITY_DRY_RUN` | `true` |
| `SCHEDULER_ENABLED` no container API | `false` |
| `API_KEY_ENABLED` | `false` |

### Superficies validadas

| Check | Resultado |
| --- | --- |
| `GET /health` | `200`, app healthy |
| `GET /api/v1/runtime/scheduler-reliability-audit` | `200`, sem 404 |
| `/metrics` | metricas novas presentes |
| Smoke read-only | OK, endpoint e metricas checados |
| Dashboard JSON | valido |
| Audit JSONL | ainda ausente |

Metricas confirmadas em `/metrics`:

- `reliability_dry_run_decisions_total`
- `reliability_mode_changes_total`
- `reliability_false_positive_candidates_total`
- `reliability_max_memory_ratio_observed`
- `reliability_max_backlog_score_observed`

### Status do audit log

`runtime-data/scheduler_reliability_audit.jsonl` continua ausente. Isso e esperado nesta validacao porque o scheduler nao esta rodando no compose ativo e nao foi chamada nenhuma rota/função que crie uma decisao artificial. O caminho persistente esta preparado: `./runtime-data` e montado em `/app/runtime-data` no servico API e no servico scheduler quando o profile `full-stack` for usado.

### Recomendacao apos deploy

Manter `KEEP_DRY_RUN_INSUFFICIENT_DATA`.

O runtime atualizado esta servindo endpoint e metricas novas, com flags seguras. Ainda nao ha janela real de audit logs, portanto nao ha base para `READY_FOR_LIMITED_ENABLEMENT`.

## Validacao runtime real com scheduler

Data: 2026-05-24

### Scheduler validado

| Item | Evidencia |
| --- | --- |
| Container scheduler | `data-core-scheduler-1` |
| Imagem scheduler | `data-core-api:latest` |
| Image ID scheduler | `e249c795f43b` |
| Status | `Up` durante a janela de observacao |
| Container API | `data-core-api-1` |
| Imagem API | `data-core-api-light:latest` |
| Image ID API | `5db6ffe9e5d4` |
| Audit path | `runtime-data/scheduler_reliability_audit.jsonl` |
| Audit file size | `2166` bytes |

O scheduler foi iniciado com:

```bash
docker compose --profile full-stack up -d --no-deps --build scheduler
```

Foi recriada somente a API depois para carregar o espelhamento observacional das metricas derivadas a partir do JSONL:

```bash
docker compose up -d --no-deps --build api
```

### Env efetivo no scheduler

| Variavel | Valor observado |
| --- | --- |
| `SCHEDULER_ENABLED` | `true` |
| `SCHEDULER_RELIABILITY_ENABLED` | `false` |
| `SCHEDULER_RELIABILITY_DRY_RUN` | `true` |

### Evidencia real do audit JSONL

O arquivo foi criado por ciclo real do scheduler, sem chamada artificial ao engine.

| Medida | Valor |
| --- | --- |
| Tamanho inicial observado | ausente |
| Primeiro evento | `alert_webhook_job`, `LOW`, `NORMAL`, `dry_run=true`, `enabled=false` |
| Crescimento observado | `717` bytes para `2166` bytes |
| Total de decisoes | `3` |
| Janela analisada | `1.0001` horas |
| Modos | `NORMAL: 3` |
| Prioridades | `LOW: 2`, `NORMAL: 1` |
| Mode changes | `0` |
| Max memory ratio | `0.0` |
| Max backlog score | `0.0` |
| False positive ratio | `0.0` |
| Corrupt lines | `0` |
| Schema errors | `0` |

Eventos observados:

- `2026-05-24T11:29:42Z` — `alert_webhook_job`, prioridade `LOW`, modo `NORMAL`.
- `2026-05-24T12:29:42Z` — `run_ecommerce_url_targets_job`, prioridade `NORMAL`, modo `NORMAL`.
- `2026-05-24T12:29:42Z` — `alert_webhook_job`, prioridade `LOW`, modo `NORMAL`.

Todos os eventos permaneceram com `dry_run=true`, `enabled=false`, `throttled=false`, `cooldown_seconds=0.0` e `batch_size=100`.

### Checks pos-ciclo

| Check | Resultado |
| --- | --- |
| `GET /api/v1/runtime/scheduler-reliability-audit` | `200`, leu 3 eventos |
| `/metrics` | metricas novas presentes e com labels reais |
| Smoke read-only | OK |
| Recomendacao | `KEEP_DRY_RUN_INSUFFICIENT_DATA` |

Metricas observadas:

- `reliability_dry_run_decisions_total{job_name="alert_webhook_job",mode="NORMAL",priority="LOW"} 2`
- `reliability_dry_run_decisions_total{job_name="run_ecommerce_url_targets_job",mode="NORMAL",priority="NORMAL"} 1`
- `reliability_mode_changes_total 0`
- `reliability_max_memory_ratio_observed 0`
- `reliability_max_backlog_score_observed 0`

### Seguranca operacional

Nenhuma protecao efetiva foi ativada. A camada calculou e registrou decisoes, mas nao aplicou throttling, cooldown ou reducao real de batch. Nao houve restart/kill automatico e nenhuma alteracao de prioridade, threshold ou logica central dos jobs.

### Recomendacao apos runtime real

Manter `KEEP_DRY_RUN_INSUFFICIENT_DATA`.

A emissao real do audit esta validada, mas a janela ainda e menor que 6 horas e o volume ainda e menor que 24 decisoes. Continuar observando com `SCHEDULER_RELIABILITY_ENABLED=false` e `SCHEDULER_RELIABILITY_DRY_RUN=true`.

## Validacao pos-janela minima

Data: 2026-05-25

### Evidencia acumulada

| Medida | Valor |
| --- | --- |
| Container scheduler | `data-core-scheduler-1` |
| Imagem scheduler | `data-core-api:latest` |
| Image ID scheduler | `sha256:e249c795f43bd43678bcb230837ed98ffe591bc56358d501525dc501a8b1cdf9` |
| Status scheduler | `Up 7 hours` |
| Audit path | `runtime-data/scheduler_reliability_audit.jsonl` |
| Audit file size | `36134` bytes |
| Janela analisada | `18.3673` horas |
| Total de decisoes | `51` |
| Modos | `NORMAL: 10`, `CRITICAL_PROTECTION: 41` |
| Prioridades | `HIGH: 29`, `NORMAL: 11`, `LOW: 11` |
| Mode changes | `1` |
| Mode changes ratio | `0.0196` |
| False positive candidates | `0` |
| False positive ratio | `0.0` |
| Corrupt lines | `0` |
| Schema errors | `0` |
| Max memory ratio observed | `0.0` |
| Max backlog score observed | `0.0` |
| Max memory growth rate | `77177.09840725065` |
| Predominant mode | `CRITICAL_PROTECTION` |
| Readiness recommendation | `DO_NOT_ENABLE_RUNTIME_UNSTABLE` |

### Gates de ativacao

| Gate | Resultado |
| --- | --- |
| Janela minima >= 6h | passou: `18.3673h` |
| Decisoes dry-run >= 24 | passou: `51` |
| Integridade do audit | passou: `corrupt_lines=0`, `schema_errors=0` |
| False positive ratio <= 2% | passou: `0.0` |
| Mode changes <= 10% | passou: `0.0196` |
| Sem `PROTECTIVE`/`CRITICAL` sem explicacao | falhou: `CRITICAL_PROTECTION` predominante |
| Readiness final | falhou: `DO_NOT_ENABLE_RUNTIME_UNSTABLE` |

O bloqueio de ativacao veio do gate de pressao/estabilidade: os eventos recentes indicam `diagnosis_state=SCHEDULER_RESTART_LOOP`, `severity=critical` e `mode=CRITICAL_PROTECTION`, mesmo com `memory_usage_ratio=0.0` e `backlog_score=0.0`. Como a camada continua com `enabled=false` e `dry_run=true`, esses valores foram apenas registrados e expostos para observabilidade; nenhuma protecao runtime foi aplicada.

### Checks finais

| Check | Resultado |
| --- | --- |
| `GET /api/v1/runtime/scheduler-reliability-audit` | `200`, recomendacao `DO_NOT_ENABLE_RUNTIME_UNSTABLE` |
| `/metrics` | metricas derivadas presentes e atualizadas |
| Smoke read-only | OK, endpoint e metricas checados |
| `py_compile` | OK |
| `pytest tests/test_scheduler_reliability.py tests/test_scheduler_watchdog.py` | `36 passed` |
| Dashboard JSON | valido |
| `ruff` | indisponivel: `No module named ruff` |

Metricas observadas em `/metrics`:

- `reliability_dry_run_decisions_total{job_name="alert_webhook_job",mode="NORMAL",priority="LOW"} 5.0`
- `reliability_dry_run_decisions_total{job_name="run_ecommerce_url_targets_job",mode="NORMAL",priority="NORMAL"} 2.0`
- `reliability_dry_run_decisions_total{job_name="normalize_job",mode="NORMAL",priority="HIGH"} 3.0`
- `reliability_dry_run_decisions_total{job_name="normalize_job",mode="CRITICAL_PROTECTION",priority="HIGH"} 26.0`
- `reliability_dry_run_decisions_total{job_name="alert_webhook_job",mode="CRITICAL_PROTECTION",priority="LOW"} 6.0`
- `reliability_dry_run_decisions_total{job_name="analytics_job",mode="CRITICAL_PROTECTION",priority="NORMAL"} 6.0`
- `reliability_dry_run_decisions_total{job_name="run_ecommerce_url_targets_job",mode="CRITICAL_PROTECTION",priority="NORMAL"} 3.0`
- `reliability_mode_changes_total 1.0`
- `reliability_max_memory_ratio_observed 0.0`
- `reliability_max_backlog_score_observed 0.0`

### Recomendacao final

Nao ativar protecao runtime agora. Manter:

- `SCHEDULER_RELIABILITY_ENABLED=false`
- `SCHEDULER_RELIABILITY_DRY_RUN=true`

Recomendacao: `DO_NOT_ENABLE_RUNTIME_UNSTABLE`.

Motivo: os gates de volume, janela, integridade, false positives e estabilidade de mudanca passaram, mas a janela real mostrou predominancia de `CRITICAL_PROTECTION` associada a `SCHEDULER_RESTART_LOOP`. Antes de qualquer ativacao limitada, investigar a causa do restart loop/estado critico e repetir uma nova janela de calibracao em dry-run ate que o modo predominante volte a `NORMAL` ou, no maximo, `CONSERVATIVE` explicado por pressao real.
