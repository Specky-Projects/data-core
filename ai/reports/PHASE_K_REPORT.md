# Phase K Report — Crypto Research Expansion

> Gerado: 2026-05-16
> Status: **COMPLETO**

---

## Objetivo (Track B — Crypto)

Expandir a plataforma de pesquisa quantitativa com:
- Dashboard consolidado de métricas de pesquisa
- Comparação formal de estratégias
- Cenários nomeados de replay
- Organização de experimentos com tags/lineage
- Simulação de portfólio multi-estratégia
- Expansão de QA de datasets
- Observabilidade quantitativa (8 novas métricas Prometheus)

---

## Arquivos Modificados / Criados

### domains/crypto_coin/research/

| Arquivo | Mudança |
|---|---|
| `scenario_runner.py` | **NOVO** — 6 cenários nomeados com CLI |
| `portfolio_simulator.py` | **NOVO** — simulação multi-estratégia ponderada |
| `experiment_tracker.py` | +`tags`, `group_id`, `parent_run_id` em `ExperimentRecord`; filtros em `load_all()`/`compare()` |
| `strategy_ranker.py` | +`compare_head_to_head()`, `update_prometheus_scores()`, `rank()` atualiza Prometheus |
| `sweep_runner.py` | Emite `sweep_runs_total` + `sweep_combinations_tested_total`; grava tags e group_id |

### domains/crypto_coin/analytics/

| Arquivo | Mudança |
|---|---|
| `dataset_qa.py` | `_build_summary()` agora emite `dataset_qa_fleet_score` + `dataset_qa_critical_count` |

### api/

| Arquivo | Mudança |
|---|---|
| `metrics.py` | 8 novas métricas Prometheus (sweep, experiments, scores, scenarios, portfolio, fleet) |

### grafana/dashboards/

| Arquivo | Mudança |
|---|---|
| `crypto_research.json` | **NOVO** — 14 painéis em 5 rows para pesquisa quantitativa |

### ai/

| Arquivo | Mudança |
|---|---|
| `ai/contexts/research_behavior_status.md` | +Phase K section Track B |
| `ai/contexts/evolution_status.md` | Crypto Research Layer: L3 → L4 |
| `ai/reports/PHASE_K_REPORT.md` | Este arquivo |

---

## Novas Métricas Prometheus

| Métrica | Tipo | Descrição |
|---|---|---|
| `sweep_runs_total` | Counter | Grid searches executados |
| `sweep_combinations_tested_total` | Counter | Combinações de parâmetros testadas |
| `experiment_records_total` | Counter | Experimentos persistidos em JSONL |
| `strategy_composite_score` | Gauge | Score composto atual por estratégia |
| `scenario_runs_total` | Counter | Runs por cenário nomeado |
| `portfolio_simulations_total` | Counter | Simulações de portfólio |
| `dataset_qa_fleet_score` | Gauge | Score médio de integridade da frota OHLCV |
| `dataset_qa_critical_count` | Gauge | Pares em estado CRITICAL |

---

## Cenários Disponíveis

```
bull_market     Jan-Abr 2021  — tendência de alta sustentada
bear_market     Jun-Dez 2022  — queda + capitulação
sideways        Set-Out 2023  — mercado lateral
high_vol        Jan 2024      — volatilidade extrema (ETF)
news_shock      Nov 2022      — colapso FTX
post_halving    Abr-Jul 2024  — pós-halving
```

```bash
# Executar cenário
python -m domains.crypto_coin.research.scenario_runner \
  --scenario bull_market --strategy trend_following --symbol BTC/USDT

# Comparar estratégias head-to-head
python -m domains.crypto_coin.research.strategy_ranker \
  --head-to-head trend_following breakout_scalper

# Simulação de portfólio
python -m domains.crypto_coin.research.portfolio_simulator \
  --weights trend_following:0.5 breakout_scalper:0.5 --symbol BTC/USDT
```

---

## Maturidade

| Domínio | Antes | Depois |
|---|---|---|
| Crypto Research Layer | L3 | **L4** |

**L4**: Pesquisa quantitativa completa com cenários, portfólio, comparação formal,
tags/lineage, Prometheus wired, Grafana dashboard dedicado.

---

## Gaps Pendentes

| Gap | Prioridade |
|---|---|
| Scenario runner com período exato (start_date/end_date filtrado no DB) | P2 |
| Portfolio equity curve combinada (requer mesmo período de dados) | P3 |
| Prometheus multi-process — Pushgateway para worker metrics (H-H-10) | P3 |
