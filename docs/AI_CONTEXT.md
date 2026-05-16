# AI Context — data-core

> Este arquivo foi substituido. O contexto operacional completo esta em:
>
> **`ai/CONTEXT.md`** — contexto operacional (topologia, tabelas, arquivos-chave, gaps)
> **`ai/RUNBOOK.md`** — playbook: diagnosticar, deployar, ativar dominio, resetar circuit breaker
> **`ai/DOC_SYNC_RULES.md`** — regras de sincronizacao de documentacao

---

## Resumo rapido (Phase A — 2026-05-16)

- 3 containers: `api`, `scheduler`, `worker`
- Migracao atual: `0015_pipeline_observability` (pipeline_runs + pipeline_failures)
- Crypto: operacional (5 pairs x 2 TF, coletando a cada 15min)
- Outros dominios: demo/stub
- Health probes: `/live`, `/ready`, `/health`
- Prometheus: `/metrics` com 14+ metrics de pipeline
- Grafana: `data-core-ops-v1` importado em producao
- Leia `ai/CONTEXT.md` para estado completo.
