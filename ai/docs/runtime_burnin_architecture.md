# Runtime Burn-In Architecture — Phase S

## Visão Geral

A Phase S implementa uma camada de validação de estabilidade que roda **por cima** da infraestrutura da Phase R sem modificá-la. Todos os módulos S são somente leitura em relação ao runtime — eles leem arquivos JSONL, calculam scores, e escrevem seus próprios logs de validação.

```
┌─────────────────────────────────────────────────────┐
│                  Phase S — Burn-In Layer            │
│                                                     │
│  S-9 Orchestrator (autonomous_runtime_stability)    │
│    ├── S-1 RuntimeBurninEngine                      │
│    ├── S-2 MetricsIntegrityValidator                │
│    ├── S-3 GrafanaDashboardValidator                │
│    ├── S-4 CollectorReliabilityEngine               │
│    ├── S-5 ReplayIntegrityBurninValidator           │
│    ├── S-6 IncidentNoiseReductionEngine             │
│    ├── S-7 ColdStartResilienceValidator             │
│    └── S-8 OperationalDriftAnalyzer                 │
│                                                     │
└──────────────────────┬──────────────────────────────┘
                       │ lê data/*.jsonl (somente leitura)
                       ▼
┌─────────────────────────────────────────────────────┐
│                  Phase R — Runtime Layer            │
│  R-1 Startup │ R-2 State │ R-3 Watchdog            │
│  R-4 Stability │ R-5 Deploy │ R-6 Incidents        │
│  R-7 Recovery │ R-8 Governance │ R-9 Classifier    │
└─────────────────────────────────────────────────────┘
                       │ escreve data/*.jsonl
                       ▼
┌─────────────────────────────────────────────────────┐
│               Phase Q — Live Monitoring Layer       │
│  Guardian │ Watchdog │ Capital Preservation         │
│  Execution Audit │ Live Readiness                  │
└─────────────────────────────────────────────────────┘
```

## Fases de Burn-In (S-1)

```
Tempo de Uptime
0h ──────── 4h ──────── 24h ──────── 72h ──────────▶
│WARMING_UP │STABILIZING │  BURN_IN  │   MATURE      │
│ score×0.3 │  score×0.6 │ score×0.8 │  score×1.0    │
```

O score final é **atenuado** durante fases iniciais para evitar falsos positivos de estabilidade em sistemas recém-iniciados.

## Fluxo de Dados

```
data/*.jsonl (escritos por Phase Q/R)
       │
       ▼
S-1 RuntimeBurninEngine.evaluate()
   → lê: stability_log, watchdog_log, metrics_integrity_log
   → calcula: burnin_stability_score, runtime_burnin_score
   → escreve: data/runtime_burnin_log.jsonl

S-2 MetricsIntegrityValidator.validate()
   → verifica: mtime de 20 arquivos JSONL fonte
   → calcula: metrics_integrity_score (fresh/total)
   → escreve: data/metrics_integrity_log.jsonl

S-3..S-8: similar pattern
       │
       ▼
S-9 AutonomousRuntimeStabilityOrchestrator.run()
   → agrega scores de S-1..S-8
   → escreve: data/runtime_stability_log.jsonl
              data/runtime_stability_summary.jsonl (latest only)
       │
       ▼
api/burnin_metrics.py (Prometheus Gauges)
       │
       ▼
api/live_metrics_updater.refresh_burnin_metrics()
   → popula Gauges no processo do API
       │
       ▼
Grafana: crypto_runtime_burnin.json
```

## Score Aggregation (S-9)

```python
observability_readiness  = S2×0.40 + S3×0.30 + S4×0.30
burnin_readiness         = S1×0.50 + S5×0.30 + S6×0.20
runtime_stability        = mean(S1..S8)
burnin_op_maturity       = stability×0.35 + obs×0.30 + burnin×0.20
                         + cold_start×0.10 + drift×0.05
```

## Critérios de Graduação

| Métrica | Verde | Amarelo | Vermelho |
|---|---|---|---|
| burnin_stability_score | ≥85 | 70-84 | <70 |
| metrics_integrity_score | ≥90 | 70-89 | <70 |
| collector_reliability_score | ≥85 | 60-84 | <60 |
| cold_start_resilience_score | ≥85 (B) | 70-84 (C) | <70 (D/F) |
| operational_drift_score | ≥85 | 70-84 | <70 |
| burnin_operational_maturity_score | ≥80 | 60-79 | <60 |

## Arquivos Relevantes

| Módulo | Arquivo |
|---|---|
| S-1 | `domains/crypto_coin/research/runtime_burnin_engine.py` |
| S-2 | `domains/crypto_coin/research/metrics_integrity_validator.py` |
| S-3 | `domains/crypto_coin/research/grafana_dashboard_validator.py` |
| S-4 | `domains/crypto_coin/research/collector_reliability_engine.py` |
| S-5 | `domains/crypto_coin/research/replay_integrity_burnin_validator.py` |
| S-6 | `domains/crypto_coin/research/incident_noise_reduction_engine.py` |
| S-7 | `domains/crypto_coin/research/cold_start_resilience_validator.py` |
| S-8 | `domains/crypto_coin/research/operational_drift_analyzer.py` |
| S-9 | `domains/crypto_coin/research/autonomous_runtime_stability_orchestrator.py` |
| S-10 | `api/burnin_metrics.py` |
| Bridge | `api/live_metrics_updater.py` → `refresh_burnin_metrics()` |
| Dashboard | `grafana/dashboards/crypto_runtime_burnin.json` |
