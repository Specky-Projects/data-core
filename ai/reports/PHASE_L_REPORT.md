# Phase L Report — Research Intelligence Layer

> Gerado: 2026-05-16
> Status: **COMPLETO**

---

## Objetivo (Track B — Crypto Research)

Elevar a plataforma de pesquisa quantitativa de L4 → L5 com:
- Orquestração completa do pipeline de pesquisa
- Camada de inteligência por estratégia (degradação, overfitting, fragilidade)
- Inteligência de portfólio (rebalanceamento, correlação, regime-aware)
- Inteligência de dataset (reliability ranking, drift persistence)
- Inteligência de cenários (stress score, chained scenarios)
- Dashboard executivo quantitativo (Grafana)
- 8 novas métricas Prometheus

---

## Arquivos Criados / Modificados

### domains/crypto_coin/research/

| Arquivo | Mudança |
|---|---|
| `research_orchestrator.py` | **NOVO** — Orchestrator: sweep+cenários+ranking+QA+portfolio com lineage |
| `strategy_intelligence.py` | **NOVO** — Degradação/overfit/fragilidade/regime/consistency_score |
| `portfolio_intelligence.py` | **NOVO** — Vol targeting, exposure balance, correlação, regime-aware |
| `scenario_intelligence.py` | **NOVO** — Stress score (0–100), chained scenarios, stress report |

### domains/crypto_coin/analytics/

| Arquivo | Mudança |
|---|---|
| `dataset_intelligence.py` | **NOVO** — Exchange/pair reliability ranking, drift persistence |

### api/

| Arquivo | Mudança |
|---|---|
| `metrics.py` | +8 novas métricas Prometheus (Phase L FASE 14) |

### grafana/dashboards/

| Arquivo | Mudança |
|---|---|
| `crypto_quant_executive.json` | **NOVO** — Dashboard executivo: 6 rows, 13 painéis |

### ai/

| Arquivo | Mudança |
|---|---|
| `ai/contexts/research_behavior_status.md` | +Phase L Track B section |
| `ai/contexts/evolution_status.md` | Crypto Research Layer L4 → L5 |
| `ai/reports/PHASE_L_REPORT.md` | Este arquivo |

---

## Novas Métricas Prometheus (Phase L)

| Métrica | Tipo | Labels | Descrição |
|---|---|---|---|
| `orchestration_runs_total` | Counter | success | Pipeline orchestrator runs |
| `strategy_degradation_total` | Counter | strategy_id, severity | Degradation signals |
| `portfolio_rebalance_total` | Counter | rebalance_type | Simulações de rebalanceamento |
| `dataset_drift_score` | Gauge | symbol, timeframe | Drift magnitude por par |
| `replay_stress_total` | Counter | scenario, strategy_id | Stress replay executions |
| `scenario_stress_score` | Gauge | scenario, strategy_id | Score de stress (0–100) |
| `strategy_consistency_score` | Gauge | strategy_id | Consistency score (0–100) |
| `portfolio_correlation_avg` | Gauge | — | Correlação média entre estratégias |

---

## CLI Commands

```bash
# Orchestration — pipeline completo
python -m domains.crypto_coin.research.research_orchestrator \
  --strategy trend_following breakout_scalper --full --save

# Strategy Intelligence — análise completa
python -m domains.crypto_coin.research.strategy_intelligence --all

# Strategy Intelligence — apenas com alertas
python -m domains.crypto_coin.research.strategy_intelligence --all --alert

# Portfolio Intelligence — vol targeting + correlação + regime
python -m domains.crypto_coin.research.portfolio_intelligence \
  --strategies trend_following breakout_scalper \
  --rebalance vol_target --correlation --regimes

# Dataset Intelligence — reliability report
python -m domains.crypto_coin.analytics.dataset_intelligence --reliability-report

# Dataset Intelligence — par específico com drift
python -m domains.crypto_coin.analytics.dataset_intelligence \
  --pair BTC/USDT --tf 15m --drift

# Scenario Intelligence — stress report
python -m domains.crypto_coin.research.scenario_intelligence \
  --strategy trend_following --stress-report

# Scenario Intelligence — chain bull → shock → sideways
python -m domains.crypto_coin.research.scenario_intelligence \
  --strategy trend_following \
  --chain bull_market news_shock sideways
```

---

## Grafana Dashboard (crypto_quant_executive.json)

| Row | Painéis | Métricas |
|---|---|---|
| 🏆 Top Strategies | Composite + Consistency bargauge | `strategy_composite_score`, `strategy_consistency_score` |
| 📉 Degradation | Events stat + Orchestration + timeseries | `strategy_degradation_total`, `orchestration_runs_total` |
| 📊 Portfolio | Correlation gauge + Simulations + Rebalances + Piechart | `portfolio_correlation_avg`, `portfolio_rebalance_total` |
| 🎯 Scenario Stress | Stress bargauge + Replay timeseries | `scenario_stress_score`, `replay_stress_total` |
| 🗃️ Dataset | Fleet score + Critical count + Drift | `dataset_qa_fleet_score`, `dataset_drift_score` |
| 🔬 Lineage | Records stat + Sweep timeseries | `experiment_records_total`, `sweep_runs_total` |

---

## Maturidade

| Domínio | Antes | Depois |
|---|---|---|
| Crypto Research Layer | L4 | **L5** |

**L5**: Pipeline orquestrado + camada de inteligência completa (degradação, overfitting, fragilidade, correlação, regime, drift, stress) + executive dashboard + 16 métricas Prometheus total.

---

## Gaps Pendentes (Phase M)

| Gap | Prioridade |
|---|---|
| Scenario runner com datas exatas (start_date/end_date filtrado no DB) | P2 |
| Portfolio equity curve combinada (mesmo período temporal) | P3 |
| Prometheus multi-process — Pushgateway para worker metrics | P3 |
| ExperimentTracker → PostgreSQL migration (atual JSONL) | P3 |
| ResearchOrchestrator scheduling automático (cron semanal) | P3 |
