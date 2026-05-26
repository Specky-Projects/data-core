# EVOLUTION MATRIX — Poupi Platform

> Generated: 2026-05-16 | Phase G — Product Validation & Crypto Research Layer
>
> Evolução do MATURITY_MATRIX (Phase F): classifica cada domínio contra
> critérios de dados, analytics, replay, observabilidade, produto e readiness.

---

## Legenda de Maturidade

| Nível | Critério |
|---|---|
| `L0` | Inexistente ou quebrado |
| `L1` | Funcional, sem observabilidade ou analytics |
| `L2` | Funcional + observabilidade básica + métricas |
| `L3` | Hardened: resiliente, rastreável, replay possível |
| `L4` | Production-ready: usuários reais, SLA, runbook, testes E2E |

---

## Matriz Principal

| Domínio | Dados | Analytics | Replay | Observabilidade | Produto | Readiness |
|---|---|---|---|---|---|---|
| **Ecommerce pipeline** | L3 | L2 | L1 | L2 | L2 | `L2` |
| **Crypto OHLCV pipeline** | L2 | L3 | **L3** | L3 | L1 | `L3` |
| **TradingBot v4** | L3 | L4 | L3 | L2 | L1 | `L3` |
| **poupi-baby alertas** | L2 | L2 | L1 | **L3** | L2 | `L2` |
| **poupi-baby watchlist** | L2 | L1 | L1 | **L2** | L2 | `L2` |
| **poupi-baby oportunidades** | L2 | **L3** | L1 | L2 | **L2** | `L2` |
| **Real Estate pipeline** | L2 | L1 | L1 | L1 | L0 | `L1` |
| **Sports Odds** | L0 | L0 | L0 | L0 | L0 | `L0` |

> **Negrito** = evolução nesta fase

---

## Detalhe por Domínio

### Ecommerce Pipeline

| Dimensão | Nível | Evidência |
|---|---|---|
| Dados | L3 | 17 targets VTEX, source_url, canonical_product_id, PriceHistory |
| Analytics | L2 | avg7d/30d, min/max90d, price_score (z-score) |
| Replay | L1 | Sem replay histórico; dados em Postgres mas sem engine |
| Observabilidade | L2 | collection_raw_saved/duplicates, pipeline_runs, pipeline_stage_* |
| Produto | L2 | price-feed exposto, poupi-baby consumindo, alertas funcionais |

### Crypto OHLCV Pipeline (data-core)

| Dimensão | Nível | Evidência |
|---|---|---|
| Dados | L2 | 5 pares × 2 TF, UniqueConstraint dedup, 90d retention |
| Analytics | L3 | RSI/MA/ATR/ADX/signal/regime/confidence — TradingAnalyticsProcessor |
| Replay | **L3** | `db_replay.py` — replay offline de normalized_market_candles [G-03] |
| Observabilidade | L3 | trading_signal_total, trading_regime_total, trading_confidence_score [F-03]; backtest_runs_total, ohlcv_integrity [G-04] |
| Produto | L1 | Consumido por poupi-crypto internamente; sem produto público |

### TradingBot v4

| Dimensão | Nível | Evidência |
|---|---|---|
| Dados | L3 | SQLite 8 tabelas: trades, signals, equity, shadow, regime, entry_ctx |
| Analytics | L4 | Sharpe, **Sortino** [G-01], **Calmar** [G-01], drawdown, MAE/MFE, win rate, B&H, expectancy, profit_factor |
| Replay | L3 | simulation.py (realistic mode, walk-forward, intracandle SL/TP, bar+1) |
| Observabilidade | L2 | SQLite logs + Telegram notifier; sem Prometheus nativo |
| Produto | L1 | Paper trading apenas; sem produto público |

### poupi-baby Alertas (event-driven + cron)

| Dimensão | Nível | Evidência |
|---|---|---|
| Dados | L2 | PriceHistory, UserEvent cooldown, Alert.targetPrice |
| Analytics | L2 | NEW_LOWEST_PRICE, PRICE_DROP (5%), isHistoricalLowest |
| Replay | L1 | Sem replay; CheckAlertsService é polling |
| Observabilidade | **L3** | alertsDispatched (ambos paths) [F-01], notificationDelivered, **notificationEngaged** CTR [G-05] |
| Produto | L2 | BullMQ retry, cooldown, Telegram+email funcionais |

### poupi-baby Watchlist

| Dimensão | Nível | Evidência |
|---|---|---|
| Dados | L2 | ON CONFLICT dedup, soft delete, product existence check |
| Analytics | L1 | Sem score ou histórico na listagem |
| Replay | L1 | — |
| Observabilidade | **L2** | **watchlistActions** counter [G-05] |
| Produto | L2 | CRUD completo, auth guard, integração com produtos |

### poupi-baby Opportunity Engine

| Dimensão | Nível | Evidência |
|---|---|---|
| Dados | L2 | PriceHistory (min 3 pontos), all-time low, avg90d |
| Analytics | **L3** | DealScore: 5 componentes (desconto, ATL, estabilidade, tendência, raridade) [G-06]; **endpoint /deal-score/opportunities** [G-06] |
| Replay | L1 | — |
| Observabilidade | L2 | BullMQ deal-score queue + notificationDelivered |
| Produto | **L2** | Endpoint público (autenticado), score explicável, labels/emojis para UI |

---

## Implementações Phase G

### Trilha A — Poupi Baby

| ID | Fase | Implementação | Arquivo(s) |
|---|---|---|---|
| G-01 | Fase 3 | `notificationEngaged` counter (CTR) em MetricsService | `metrics/metrics.service.ts` |
| G-02 | Fase 3 | `watchlistActions` counter em MetricsService + AlertsService | `metrics/metrics.service.ts`, `alerts/alerts.service.ts` |
| G-03 | Fase 3 | `NotificationTrackingService` — token, UserEvent, métricas | `notifications/tracking/notification-tracking.service.ts` |
| G-04 | Fase 3 | `NotificationTrackingController` — GET /notifications/track (pixel/redirect) | `notifications/tracking/notification-tracking.controller.ts` |
| G-05 | Fase 3 | Registro no NotificationsModule | `notifications/notifications.module.ts` |
| G-06 | Fase 4 | `DealScoreService.getTopOpportunities()` | `deal-score/deal-score.service.ts` |
| G-07 | Fase 4 | `GET /deal-score/opportunities?limit=20&minScore=60` | `deal-score/deal-score.controller.ts` |

### Trilha B — Crypto

| ID | Fase | Implementação | Arquivo(s) |
|---|---|---|---|
| G-08 | Fase 9 | `sortino_ratio()`, `calmar_ratio()`, `exposure_pct()` | `analytics/metrics/calc.py` |
| G-09 | Fase 9 | `compute_all()` expandido (sortino, calmar, win_count, loss_count) | `analytics/metrics/calc.py` |
| G-10 | Fase 8 | `OHLCVIntegrityReport` + `check_integrity()` + `check_all_symbols()` | `analytics/ohlcv_integrity.py` |
| G-11 | Fase 7 | `db_replay.py` — replay offline de normalized_market_candles | `backtesting/db_replay.py` |
| G-12 | Fase 10 | Métricas: `backtest_runs_total`, `backtest_duration_seconds`, `ohlcv_integrity_checks_total`, `ohlcv_gaps_detected_total` | `api/metrics.py` |

---

## Gaps Remanescentes (pós-Phase G)

| ID | Gap | Domínio | Impacto | Prioridade |
|---|---|---|---|---|
| G-H-01 | Zero usuários reais em poupi-baby | poupi-baby | KPI principal bloqueado | Alta |
| G-H-02 | Token de tracking não gerado nos templates de email ainda | notificações | CTR sempre zero | Média |
| G-H-03 | `TradingBot` sem Prometheus externo — métricas em SQLite | crypto | Visibilidade limitada | Média |
| G-H-04 | OHLCV integrity checker não integrado ao scheduler (só CLI) | crypto | Alertas de degradação de dados | Média |
| G-H-05 | Backtest metrics (`backtest_runs_total`) não wired no runner | crypto | Prometheus sempre zero | Média |
| G-H-06 | Real estate analytics parcial (neighborhood NULL) | real_estate | Analytics incompletas | Baixa |
| G-H-07 | Sports odds inteiramente desativado | sports_betting | Domínio inativo | Baixa |
| G-H-08 | Crypto snapshot path (CryptoAnalyticsProcessor) STUB | crypto | Snapshot analytics NULL | Média |
| G-H-09 | DB replay não cobre funding rate / open interest | crypto | Replay incompleto para estratégias avançadas | Baixa |
| G-H-10 | Prometheus multi-process gap (scheduler/worker ≠ API process) | todos | Pushgateway necessário | Média |

---

## Evolução por Fase (histórico)

| Fase | Foco | Evolução Principal |
|---|---|---|
| Phase D | Scraping Audit | schedulable=False em mocks; prometheus.yml corrigido; log padronizado |
| Phase E | Data Validation | E-01 (metrics wired), E-03 (UniqueConstraint), E-04 (source_url); READINESS_MATRIX |
| Phase F | Internal Validation + Crypto Hardening | F-01/F-02 (alertsDispatched), F-03 (trading Prometheus); MATURITY_MATRIX |
| Phase G | Product Validation + Research Layer | CTR tracking, Opportunities, DB Replay, OHLCV Integrity, Sortino/Calmar; EVOLUTION_MATRIX |

---

*Gerado em Phase G — Product Validation & Crypto Research Layer*
