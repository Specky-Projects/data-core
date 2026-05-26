# Observability Validation Flow — Phase S

## Problema

Gauges Prometheus podem mostrar valores válidos mesmo quando a fonte de dados parou de ser atualizada. Um sistema pode aparentar saúde enquanto todos os collectors estão mortos — os valores do Grafana simplesmente não mudam.

## Solução Phase S

Três módulos complementares validam diferentes camadas da observabilidade:

```
Camada 1: Métricas Prometheus (S-2)
  → "Os arquivos fonte das métricas estão frescos?"

Camada 2: Dashboards Grafana (S-3)
  → "Os dashboards têm estrutura válida para visualizar?"

Camada 3: Collectors JSONL (S-4)
  → "Os pipelines de coleta estão ativos e produzindo dados?"
```

## S-2 — Metrics Integrity Validator

### Mecanismo
```python
# Para cada métrica em METRIC_SOURCES (20 entradas):
age_min = (now.timestamp() - os.path.getmtime(source_file)) / 60

if age_min < stale_threshold:
    status = "fresh"
else:
    status = "stale"
```

### Por que mtime?
O `mtime` do arquivo JSONL é atualizado sempre que o módulo correspondente escreve um novo registro. Se o módulo parou, o arquivo envelhece. É um proxy confiável de "o daemon ainda está vivo".

### Limiares
- **Operacional** (60 min): módulos que rodam por ciclo (guardian, governance, watchdog...)
- **Research** (120 min): módulos que rodam sob demanda (deployment validator, recovery engine...)

### Score Formula
```
metrics_integrity_score  = (fresh / total) × 100
metrics_continuity_score = (fresh×1.0 + stale×0.5) / total × 100
observability_health     = integrity×0.6 + (100 se importer healthy, 40 se não) × 0.4
```

## S-3 — Grafana Dashboard Validator

### O que é validado por painel
```
1. title ≠ ""
2. gridPos presente (x, y, w, h)
3. datasource configurado (uid ou type não vazio)
4. targets[].expr não vazio (exceto panels: text, news, row, logs, dashlist)
5. Para gauge/stat/bargauge: fieldConfig.defaults.thresholds.steps ≥ 2
```

### Dashboard Integrity Score
```
healthy_expected = dashboards com filename in EXPECTED_DASHBOARDS e healthy=True
dashboard_integrity_score = (healthy_expected / len(EXPECTED_DASHBOARDS)) × 100
```

Dashboards extras (não esperados) não penalizam — só os 3 esperados contam.

### Visualization Consistency Score
```
visualization_consistency = 100 - (missing × 15) - (corrupt × 25)
```

Dashboards corrompidos (JSON inválido) penalizam mais do que os ausentes.

## S-4 — Collector Reliability Engine

### Buckets de Freshness
```
< 1h  → fresh   (peso 1.0)
1-6h  → recent  (peso 0.7)
6-24h → stale   (peso 0.3)
> 24h → dead    (peso 0.0)
missing → (peso 0.0)
```

### Score Formulas
```
collector_reliability_score  = (fresh + recent) / total × 100
normalization_integrity_score = (1 - parse_errors / total_lines) × 100
data_freshness_score          = Σ(peso × 1) / total × 100
```

### Core Collectors
8 arquivos são considerados "core" — sua ausência gera issue crítica:
```
data/live_governance_summary.jsonl
data/live_execution_audit_summary.jsonl
data/live_guardian_log.jsonl
data/live_capital_preservation_log.jsonl
data/live_readiness_revalidation_log.jsonl
data/watchdog_log.jsonl
data/runtime_governance_log.jsonl
data/stability_log.jsonl
```

## Cluster Score (S-9)

```
observability_readiness_score = S2×0.40 + S3×0.30 + S4×0.30
```

Se qualquer um dos três for verde (≥85), o cluster se mantém acima de 70% mesmo com um módulo amarelo.

## Sequência de Diagnóstico

```
observability_readiness < 80?
  ├── S-4 collector_reliability < 70?
  │     → collectors mortos/stale → reiniciar daemons de coleta
  ├── S-2 metrics_integrity < 70?
  │     → métricas stale → verificar app/main.py scheduler
  └── S-3 dashboard_integrity < 100?
        → dashboards corrompidos/ausentes → regenerar JSONs
```
