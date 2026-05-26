# Scheduler adaptive protection runbook

## Diagnostico

```bash
curl -H "X-API-Key: $API_KEY" http://data-core-api:8000/api/v1/runtime/scheduler-protection | jq .
curl -H "X-API-Key: $API_KEY" http://data-core-api:8000/api/v1/runtime/scheduler-reliability-audit | jq .
curl -H "X-API-Key: $API_KEY" http://data-core-api:8000/api/v1/runtime/scheduler-diagnosis | jq .
grep scheduler_reliability_audit runtime-data/scheduler_reliability_audit.jsonl
python scripts/scheduler_reliability_smoke.py --base-url http://data-core-api:8000
docker stats --no-stream scheduler-dvq6dwsagsw4p4oqwuw7bak9-103248396421
```

## Ativacao segura

1. Manter `SCHEDULER_RELIABILITY_ENABLED=false` e observar metricas.
2. Habilitar `SCHEDULER_RELIABILITY_ENABLED=true` com `SCHEDULER_RELIABILITY_DRY_RUN=true`.
3. Confirmar que recomendacoes e modos batem com a pressao real.
4. Exigir `false_positive_ratio <= 0.02`, `normal_stable=true` e baixa oscilacao.
5. Somente depois considerar ativacao parcial conservadora.
6. Somente depois de nova janela estavel considerar `SCHEDULER_RELIABILITY_DRY_RUN=false`.

## Criterios objetivos

Antes de qualquer ativacao futura:

- minimo de 6 horas de `runtime-data/scheduler_reliability_audit.jsonl`;
- minimo de 24 decisoes dry-run;
- 0 linhas corrompidas e 0 erros de schema;
- `false_positive_ratio <= 0.02`;
- `mode_changes_total / total_events <= 0.10`;
- `CRITICAL_PROTECTION` somente se memoria, OOM, swap, ciclo ou backlog explicarem a decisao;
- nenhuma recomendacao destrutiva;
- metricas Prometheus presentes em `/metrics`;
- dashboard com paineis de dry-run, mode changes, max pressure e readiness;
- readiness final `READY_FOR_LIMITED_ENABLEMENT`.

## O que a camada pode fazer

- Reduzir batch size efetivo de jobs que aceitam `limit`.
- Inserir cooldown antes de jobs sob pressao.
- Aplicar delay extra em jobs `LOW`.
- Emitir metricas e audit logs.

## O que a camada nao faz

- Nao reinicia containers.
- Nao mata processos.
- Nao cancela jobs criticos.
- Nao altera estrategia crypto, sinais, providers, Redis ou BullMQ.

## Quando investigar leak

Investigar se `mode=PROTECTIVE` ou `CRITICAL_PROTECTION` vier acompanhado de `growth_rate` positivo sustentado e memoria nao retornar ao baseline apos ciclos.

## Quando nao ativar

- Audit JSONL ausente, pequeno ou com qualquer linha corrompida.
- `readiness_recommendation` diferente de `READY_FOR_LIMITED_ENABLEMENT`.
- `mode_changes_total` alto ou alternancia repetida entre `NORMAL` e modos protetivos.
- `false_positive_ratio` acima de 2%.
- Maior pressao observada ja cruza limiares de `PROTECTIVE` ou `CRITICAL_PROTECTION`.

## Rollback

Rollback operacional continua sendo manter ou restaurar:

```bash
SCHEDULER_RELIABILITY_ENABLED=false
SCHEDULER_RELIABILITY_DRY_RUN=true
```

Nao ha rollback de containers, processos ou jobs nesta camada; ela nao deve reiniciar, matar nem cancelar nada automaticamente.

## Quando escalar

Escalar host quando memoria critica, swap e backlog aparecem juntos, ou quando OOM/restart volta mesmo com batch reduzido.
