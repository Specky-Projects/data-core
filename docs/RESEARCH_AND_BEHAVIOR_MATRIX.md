# RESEARCH & BEHAVIOR MATRIX — Poupi Platform

> Generated: 2026-05-16 | Phase H — Behavior Tracking & Quant Research Infrastructure
>
> Complementa a EVOLUTION_MATRIX (Phase G): foco em infraestrutura de pesquisa
> quantitativa (Crypto) e rastreamento de comportamento do usuário (Poupi Baby).

---

## Legenda de Maturidade (herdada da EVOLUTION_MATRIX)

| Nível | Critério |
|---|---|
| `L0` | Inexistente ou quebrado |
| `L1` | Funcional, sem observabilidade ou analytics |
| `L2` | Funcional + observabilidade básica + métricas |
| `L3` | Hardened: resiliente, rastreável, replay possível |
| `L4` | Production-ready: usuários reais, SLA, runbook, testes E2E |

---

## Dimensões de Research (Trilha B)

| Componente | Antes (Phase G) | Depois (Phase H) | Gap Remanescente |
|---|---|---|---|
| Experiment Tracking | L0 — sem registro | **L2** — JSONL, run_id, métricas, registry | L3 se integrar ao scheduler |
| Strategy Registry | L0 — parâmetros em código | **L2** — YAML canônico, versionado | L3 se auto-atualizar via sweep |
| Parameter Sweep | L0 — manual | **L2** — grid search, batch replay, auto-record | L3 se paralelo (multiprocessing) |
| Regime Analytics | L1 — fetch básico no repo | **L2** — win/loss por regime, volatility buckets, transições | L3 se integrar ao dashboard |
| OHLCV Integrity | L2 — gaps, anomalias, duplicatas | **L3** — + drift, flat candles, integrity_score 0–100 + Prometheus wired | L4 se scheduled cron |
| Backtest Observability | L1 — métricas definidas mas não wired | **L3** — backtest_runs_total + duration + candles wired em db_replay | L4 se backtest_runner.py tb wired |

## Dimensões de Comportamento (Trilha A)

| Componente | Antes (Phase G) | Depois (Phase H) | Gap Remanescente |
|---|---|---|---|
| Seed Interno | L0 — sem usuários de teste | **L1** — seed script criado | L2 após executar seed |
| Behavior Tracking | L0 — sem alert.viewed/dismissed | **L2** — BehaviorTrackingService + Prometheus counter | L3 após volume de dados |
| Alert Quality | L0 — sem análise de CTR por categoria | **L2** — AlertQualityService (CTR, fatigue, top products) | L3 se exposto via endpoint admin |
| Opportunity Refinement | L2 — apenas /opportunities global | **L2+** — /category/:category endpoint | L3 com personalização por usuário |
| Grafana Provisioning | L0 — manual | **L2** — JSON provisionado, 14 painéis, datasource | L3 com alerting rules |
| Tracking Token nos Emails | L1 — endpoint pronto mas não embutido | L1 — ainda não embutido (G-H-02 persiste) | **P2 prioritário** |

---

## Matriz Consolidada por Domínio (pós-Phase H)

| Domínio | Dados | Analytics | Replay | Observabilidade | Produto | Readiness |
|---|---|---|---|---|---|---|
| **Ecommerce pipeline** | L3 | L2 | L1 | L2 | L2 | `L2` |
| **Crypto OHLCV pipeline** | L2 | L3 | **L3** | **L3** | L1 | `L3` |
| **TradingBot v4** | L3 | L4 | L3 | L2 | L1 | `L3` |
| **poupi-baby alertas** | L2 | L2 | L1 | **L3** | L2 | `L2` |
| **poupi-baby watchlist** | L2 | L1 | L1 | L2 | L2 | `L2` |
| **poupi-baby oportunidades** | L2 | **L3** | L1 | L2 | **L2** | `L2` |
| **poupi-baby comportamento** | **L2** | **L2** | L1 | **L2** | L1 | `L2` |
| **Crypto Research Layer** | L2 | **L3** | L3 | **L3** | L1 | `L3` |
| **Real Estate pipeline** | L2 | L1 | L1 | L1 | L0 | `L1` |
| **Sports Odds** | L0 | L0 | L0 | L0 | L0 | `L0` |

> **Negrito** = evolução nesta fase (H)

---

## Implementações Phase H

### Trilha A — Poupi Baby

| ID | Fase | Implementação | Arquivo(s) |
|---|---|---|---|
| H-A-01 | Fase 1 | Seed script — usuários internos, watchlists, alertas | `src/seed/seed-internal-users.ts` |
| H-A-02 | Fase 2 | `BehaviorTrackingService` — event types: alert.viewed, alert.dismissed, product.saved, category.followed | `src/analytics/behavior-tracking.service.ts` |
| H-A-03 | Fase 2 | `behaviorEvents` counter em MetricsService | `src/metrics/metrics.service.ts` |
| H-A-04 | Fase 3 | `AlertQualityService` — CTR por categoria, fatigue report, top engaged products | `src/analytics/alert-quality.service.ts` |
| H-A-05 | Fase 3 | AnalyticsModule registra BehaviorTrackingService + AlertQualityService | `src/analytics/analytics.module.ts` |
| H-A-06 | Fase 4 | `DealScoreService.getByCategory()` — oportunidades por categoria | `src/deal-score/deal-score.service.ts` |
| H-A-07 | Fase 4 | `GET /deal-score/category/:category` endpoint | `src/deal-score/deal-score.controller.ts` |
| H-A-08 | Fase 5 | Grafana provisioning: datasource, dashboard.yml, poupi_baby.json (14 painéis) | `grafana/provisioning/` |

### Trilha B — Crypto Research

| ID | Fase | Implementação | Arquivo(s) |
|---|---|---|---|
| H-B-01 | Fase 6 | `ExperimentRecord` + `ExperimentTracker` — JSONL persistence, compare, best, summary | `research/experiment_tracker.py` |
| H-B-02 | Fase 7 | `strategy_registry.yaml` — 4 estratégias (trend_following, breakout_scalper, mean_reversion, shadow_tester) | `research/strategy_registry.yaml` |
| H-B-03 | Fase 7 | `StrategyRegistry` — interface Python para o YAML | `research/strategy_registry.py` |
| H-B-04 | Fase 8 | `sweep_runner.py` — parameter grid search + batch replay, auto-record no ExperimentTracker | `research/sweep_runner.py` |
| H-B-05 | Fase 9 | `regime_analytics.py` — win/loss por regime, volatility buckets, transições | `analytics/regime_analytics.py` |
| H-B-06 | Fase 10 | OHLCV integrity: + timeframe drift, flat candles, `integrity_score` 0–100 | `analytics/ohlcv_integrity.py` |
| H-B-07 | Fase 11 | Wire `backtest_runs_total` + `backtest_duration_seconds` + `backtest_candles_processed_total` em `db_replay.py` | `backtesting/db_replay.py` |
| H-B-08 | Fase 11 | Wire `ohlcv_integrity_checks_total` + `ohlcv_gaps_detected_total` em `ohlcv_integrity.py` | `analytics/ohlcv_integrity.py` |
| H-B-09 | Fase 11 | `strategy_params` override em `replay_from_db()` para sweep_runner | `backtesting/db_replay.py` |

---

## Gaps Remanescentes (pós-Phase H)

| ID | Gap | Domínio | Impacto | Prioridade |
|---|---|---|---|---|
| H-H-01 | Seed de usuários internos não executado (script criado, precisa rodar) | poupi-baby | KPI principal | Alta |
| H-H-02 | Token de tracking não embutido nos templates de email (G-H-02 persiste) | notificações | CTR sempre zero | **Alta** |
| H-H-03 | AlertQualityService não exposto via endpoint (serviço existe, sem controller) | analytics | Dashboard admin indisponível | Média |
| H-H-04 | backtest_runner.py (online/Binance) não tem métricas wired (só db_replay tem) | crypto | Prometheus parcial | Média |
| H-H-05 | sweep_runner.py não paralelo — grid search sequencial | research | Sweep lento para grids grandes | Baixa |
| H-H-06 | Grafana sem alerting rules (painéis prontos mas sem alertas automáticos) | observabilidade | Sem notificação proativa | Média |
| H-H-07 | BehaviorTrackingService não integrado aos controllers existentes (service criado mas não usado) | poupi-baby | behaviorEvents counter sempre zero | Média |
| H-H-08 | ExperimentTracker não chamado automaticamente no db_replay (precisa chamada explícita) | research | Experimentos não registrados automaticamente | Baixa |
| H-H-09 | regime_analytics.py não integrado ao scheduler ou dashboard | crypto | Analytics de regime só via CLI | Baixa |
| H-H-10 | Prometheus multi-process gap (G-H-10 persiste — Pushgateway necessário) | todos | Métricas de worker isoladas | Média |

---

## Arquivos Criados/Modificados em Phase H

### Poupi Baby
```
backend/src/seed/seed-internal-users.ts          [CREATED]
backend/src/analytics/behavior-tracking.service.ts [CREATED]
backend/src/analytics/alert-quality.service.ts   [CREATED]
backend/src/analytics/analytics.module.ts         [MODIFIED — + BehaviorTracking + AlertQuality]
backend/src/metrics/metrics.service.ts            [MODIFIED — + behaviorEvents counter]
backend/src/deal-score/deal-score.service.ts      [MODIFIED — + getByCategory()]
backend/src/deal-score/deal-score.controller.ts   [MODIFIED — + GET /category/:category]
grafana/provisioning/datasources/prometheus.yml   [CREATED]
grafana/provisioning/dashboards/dashboard.yml     [CREATED]
grafana/provisioning/dashboards/poupi_baby.json   [CREATED — 14 painéis]
```

### Data-Core / Crypto
```
domains/crypto_coin/research/__init__.py          [CREATED]
domains/crypto_coin/research/experiment_tracker.py [CREATED]
domains/crypto_coin/research/strategy_registry.yaml [CREATED]
domains/crypto_coin/research/strategy_registry.py [CREATED]
domains/crypto_coin/research/sweep_runner.py      [CREATED]
domains/crypto_coin/analytics/regime_analytics.py [CREATED]
domains/crypto_coin/analytics/ohlcv_integrity.py  [MODIFIED — + drift, flat, score, Prometheus]
domains/crypto_coin/backtesting/db_replay.py      [MODIFIED — + metrics wire, strategy_params, candles_count]
```

### Documentação
```
data-core/docs/RESEARCH_AND_BEHAVIOR_MATRIX.md   [CREATED — este arquivo]
data-core/ai/contexts/research_behavior_status.md [CREATED]
data-core/ai/reports/PHASE_H_REPORT.md           [CREATED]
poupi-baby/ai/contexts/current_status.md          [UPDATED]
```

---

*Gerado em Phase H — Behavior Tracking & Quant Research Infrastructure*
