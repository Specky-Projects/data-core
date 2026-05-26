# Scheduler Reliability System

Esta camada adiciona protecao adaptativa nao destrutiva ao scheduler do data-core. Ela nao reinicia containers, nao mata processos, nao altera estrategia crypto e nao muda logica de scraping/coleta. Por padrao opera em modo observacional.

## Feature flags

| Flag | Default | Efeito |
| --- | --- | --- |
| `SCHEDULER_RELIABILITY_ENABLED` | `false` | Habilita aplicacao real de cooldowns e batch sizes. |
| `SCHEDULER_RELIABILITY_DRY_RUN` | `true` | Calcula decisoes, metricas e audit logs sem aplicar alteracoes. |
| `SCHEDULER_RELIABILITY_BASE_BATCH_SIZE` | `100` | Batch normal. |
| `SCHEDULER_RELIABILITY_CONSERVATIVE_BATCH_SIZE` | `75` | Batch em modo conservador. |
| `SCHEDULER_RELIABILITY_PROTECTIVE_BATCH_SIZE` | `50` | Batch em modo protetivo. |
| `SCHEDULER_RELIABILITY_CRITICAL_BATCH_SIZE` | `25` | Batch em protecao critica. |

Rollback: definir `SCHEDULER_RELIABILITY_ENABLED=false` ou manter `SCHEDULER_RELIABILITY_DRY_RUN=true`.

## Modos

| Modo | Quando entra | Efeito permitido |
| --- | --- | --- |
| `NORMAL` | memoria, swap, backlog e ciclos normais | sem alteracao |
| `CONSERVATIVE` | memoria >60%, backlog moderado, ciclo lento ou observe-more | batch menor e cooldown leve se habilitado |
| `PROTECTIVE` | memoria >75%, swap >20%, backlog alto ou crescimento suspeito | batch menor, cooldown maior, throttle de jobs `NORMAL/LOW` |
| `CRITICAL_PROTECTION` | memoria >90%, OOM recente, restart loop, backlog critico | batch minimo e cooldown alto, sem cancelar jobs criticos |

## Prioridades

| Prioridade | Exemplos | Politica |
| --- | --- | --- |
| `CRITICAL` | operational watchdog | nunca cancelar |
| `HIGH` | normalize, cleanup | preservar execucao |
| `NORMAL` | analytics, ecommerce URL targets | pode receber pacing/batch menor |
| `LOW` | real estate diario, webhook, retention | pode receber delay extra |

## Audit log

Cada decisao e registrada em `runtime-data/scheduler_reliability_audit.jsonl` com modo, prioridade, dry-run, batch efetivo, cooldown, backlog e recomendacoes.

Durante a fase de calibracao segura, interpretar o dry-run assim:

- `mode=NORMAL` predominante com poucas mudancas de modo indica thresholds estaveis.
- `CONSERVATIVE` isolado e explicado por memoria, backlog ou ciclo lento pode ser candidato a ativacao parcial futura.
- `PROTECTIVE` ou `CRITICAL_PROTECTION` em dry-run exige mais observacao antes de qualquer efeito real.
- `false_positive_candidates_total > 0` significa que uma decisao nao-normal apareceu sem pressao suficiente; avaliar o ratio e nao ativar se o risco passar do limite.
- `growth_rate` e `backlog.growth_rate` devem ser avaliados juntos: crescimento de memoria sem backlog pode indicar leak; backlog crescendo sem throughput pode indicar starvation.

## Endpoints

```bash
curl -H "X-API-Key: $API_KEY" http://data-core-api:8000/api/v1/runtime/scheduler-protection | jq .
curl -H "X-API-Key: $API_KEY" 'http://data-core-api:8000/api/v1/runtime/scheduler-reliability-audit?last_minutes=360&mode=NORMAL&job_priority=HIGH' | jq .
python scripts/scheduler_reliability_smoke.py --base-url http://data-core-api:8000
```

`/scheduler-protection` retorna a decisao atual sem aplicar nada.
`/scheduler-reliability-audit` le o JSONL e retorna filtros, resumo agregado, ultimos eventos e relatorio operacional com recomendacao.

## Recomendacoes do relatorio

| Recomendacao | Interpretacao |
| --- | --- |
| `KEEP_DRY_RUN_INSUFFICIENT_DATA` | Ainda falta janela minima ou volume minimo de decisoes. |
| `KEEP_DRY_RUN_HIGH_FALSE_POSITIVE_RISK` | Ha decisoes nao-normais sem pressao suficiente acima do limite aceito. |
| `READY_FOR_LIMITED_ENABLEMENT` | Janela minima, schema estavel, baixa oscilacao e sem pressao protetiva sustentada. |
| `DO_NOT_ENABLE_RUNTIME_UNSTABLE` | Integridade, oscilacao, modo protetivo ou runtime ainda bloqueiam qualquer ativacao. |

## Gates minimos

| Gate | Minimo |
| --- | --- |
| Janela | 6 horas de audit log |
| Volume | 24 decisoes dry-run |
| Integridade | 0 linhas corrompidas e 0 erros de schema |
| Falso positivo | ratio <= 2% |
| Estabilidade de modo | mode changes <= 10% do volume |
| Pressao maxima | no maximo `CONSERVATIVE`; `PROTECTIVE`/`CRITICAL_PROTECTION` precisam de explicacao externa |
| Readiness | recomendacao final `READY_FOR_LIMITED_ENABLEMENT` |

## Ativacao conservadora futura

Considerar ativacao parcial somente quando:

- `SCHEDULER_RELIABILITY_ENABLED=false` ainda foi mantido durante a observacao.
- `SCHEDULER_RELIABILITY_DRY_RUN=true` permaneceu ativo durante toda a janela analisada.
- `readiness_recommendation=READY_FOR_LIMITED_ENABLEMENT`.
- `NORMAL` e predominante e `normal_stable=true`.
- `mode_changes_total` e baixo para o volume de eventos.
- `false_positive_ratio <= 0.02`.
- maior memoria, pressao e backlog observados ficaram abaixo de limiares protetivos.

Nao ativar quando:

- ha arquivo ausente, corrompido ou poucos eventos para calibrar.
- aparece `PROTECTIVE` ou `CRITICAL_PROTECTION` sustentado.
- ha oscilacao frequente entre modos.
- ha falso positivo candidato.
- memoria, swap, OOM, restart loop ou backlog ainda nao foram explicados por dados externos.

## Checklist pre-ativacao

- Confirmar que nenhum restart automatico ocorreu durante a fase.
- Confirmar que concorrencia real, scraping, trading e providers nao foram alterados.
- Revisar dashboard `Data Core Scheduler Runtime`, especialmente dry-run decisions timeline, mode changes e max observed pressure.
- Salvar a resposta de `/api/v1/runtime/scheduler-reliability-audit` no registro operacional da mudanca.
- Rodar `python scripts/scheduler_reliability_smoke.py --base-url http://data-core-api:8000`.
- Se aprovado, preparar mudanca separada para ativacao limitada e manter observacao intensiva antes de desligar dry-run.

## Garantias

- Sem restart automatico.
- Sem kill automatico.
- Sem Docker socket.
- Sem alteracao de pipeline core por default.
- Mudancas reais exigem `enabled=true` e `dry_run=false`.
