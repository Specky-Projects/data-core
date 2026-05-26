# MATURITY MATRIX — Poupi Platform

> Generated: 2026-05-16 | Phase F — Internal Validation & Crypto Hardening
>
> Evolução do READINESS_MATRIX (Phase E): classifica cada domínio e componente
> contra critérios de maturidade operacional, analytics e observabilidade.

---

## Legenda de Maturidade

| Nível | Critério |
|---|---|
| `L0 — NOT_READY` | Sem dados reais ou pipeline quebrado |
| `L1 — FUNCTIONAL` | Pipeline funcional; gaps de observabilidade/analytics |
| `L2 — OBSERVABLE` | Pipeline + métricas + logs estruturados + alertas operacionais |
| `L3 — HARDENED` | L2 + retries, dedup, circuit breaker, reconexão, position restore |
| `L4 — PRODUCTION_READY` | L3 + usuários reais, SLA definido, runbook, testes E2E |

---

## Matriz Principal

| Componente | Coleta | Analytics | Observabilidade | Resiliência | Maturidade |
|---|---|---|---|---|---|
| **Ecommerce pipeline** | ✅ 17 VTEX targets | ✅ avg7d/30d, price_score | ✅ Prometheus (E-01 fix) + pipeline_runs | ✅ checksum dedup, retry scheduler | `L2 — OBSERVABLE` |
| **Crypto OHLCV pipeline** | ✅ Binance 5 pares × 2 TF | ✅ RSI/MA/ATR/ADX/signal/regime (F-03 fix) | ✅ trading_signal/regime/confidence metrics (F-03) | ✅ UniqueConstraint dedup (E-03 fix) | `L2 — OBSERVABLE` |
| **TradingBot v4** | ✅ Binance CCXT real-time | ✅ MTF, trailing stop, sizing, shadow trades, autotune | ⚠️ SQLite-only; sem Prometheus externo | ✅ reconnect, state restore, overtrading guard | `L3 — HARDENED` |
| **Real Estate pipeline** | ✅ Apolar Playwright | ⚠️ price_per_m2 ok; neighborhood NULL | ⚠️ pipeline_runs; sem métricas específicas | ✅ retry scheduler | `L1 — FUNCTIONAL` |
| **poupi-baby sync** | ✅ price-feed 2h | ✅ DealScore + source_url (E-04 fix) | ✅ BullMQ + MetricsService | ✅ upsert dedup, retry queue | `L2 — OBSERVABLE` |
| **poupi-baby alerts (event-driven)** | — | ✅ AlertEventsListener, 24h cooldown | ✅ alertsDispatched + notificationDelivered | ✅ BullMQ retry, dead-letter | `L2 — OBSERVABLE` |
| **poupi-baby alerts (cron)** | — | ✅ CheckAlertsService, batch, cooldown | ✅ alertsDispatched (F-01 fix) | ✅ BullMQ retry, batch paginado | `L2 — OBSERVABLE` |
| **Watchlist** | — | — | ⚠️ sem métricas dedicadas | ✅ ON CONFLICT dedup, soft delete | `L1 — FUNCTIONAL` |
| **Sports Odds** | ❌ Desativado | ❌ | ❌ | ❌ | `L0 — NOT_READY` |

---

## Detalhe por Dimensão

### Dimensão 1 — Analytics Quality

| Domínio | Indicadores | Validação | Histórico | Score |
|---|---|---|---|---|
| Ecommerce | avg_7d, avg_30d, min/max_90d, price_score (z-score) | Canonical IDs por EAN/UPC/slug | `collected_at` indexado | ⭐⭐⭐ |
| Crypto OHLCV | RSI(14), MA fast(9)/slow(21), ATR(14), ADX, volume_ratio, breakout_score, signal, confidence, regime | compute_indicators() v3 real | UniqueConstraint por symbol+TF+ts | ⭐⭐⭐⭐ |
| TradingBot | MAE/MFE, equity curve, win rate, B&H comparison, setup quality, loss classification | Shadow trades, backtesting, autotune | SQLite com 8 tabelas especializadas | ⭐⭐⭐⭐⭐ |
| Real Estate | price_per_m2 | Sem agregação histórica | `collected_at` | ⭐⭐ |
| Crypto Snapshot | STUB — tudo NULL | — | — | ⭐ |

### Dimensão 2 — Observabilidade

| Componente | Prometheus | Logs estruturados | Alertas | Score |
|---|---|---|---|---|
| data-core API | ✅ `/metrics` | ⚠️ LOG_JSON não ativado | ✅ /live /ready /health | ⭐⭐⭐ |
| Collector jobs | ✅ collection_raw_saved/duplicates (E-01) | ✅ _log_job_run() padronizado (Phase D) | ⚠️ multi-process gap | ⭐⭐⭐ |
| Trading pipeline | ✅ trading_signal/regime/confidence (F-03) | ✅ PipelineRecorder + pipeline_runs | ✅ pipeline_stage_last_success | ⭐⭐⭐ |
| TradingBot | ❌ sem Prometheus | ✅ logger + append_metric jsonl | ✅ Telegram notifier | ⭐⭐ |
| poupi-baby | ✅ alertsDispatched + notificationDelivered | ✅ NestJS Logger | ✅ /healthz :3001/:3002 | ⭐⭐⭐⭐ |

### Dimensão 3 — Resiliência

| Componente | Retry | Dedup | Reconexão | Circuit breaker | Score |
|---|---|---|---|---|---|
| Ecommerce collector | ✅ scheduler dead-letter | ✅ stable_payload_hash | ✅ via scheduler retry | ✅ CollectorError | ⭐⭐⭐ |
| OHLCV collector | ✅ scheduler dead-letter | ✅ uq_norm_market_candle_identity (0014) | ✅ CCXT auto-reconnect | ✅ CollectorError | ⭐⭐⭐ |
| TradingBot | ✅ ReconnectionManager (backoff exp.) | ✅ position state restore | ✅ ReconnectionManager | ⚠️ via error log | ⭐⭐⭐⭐ |
| Notification queue | ✅ BullMQ retry automático | ✅ UserEvent cooldown | ✅ Redis | ✅ dead-letter após esgotamento | ⭐⭐⭐⭐ |
| Data-core sync (poupi-baby) | ✅ NestJS cron + BullMQ | ✅ upsert idempotente | ✅ NestJS restart | — | ⭐⭐⭐ |

---

## Bugs Corrigidos em Phase F

| Bug ID | Descrição | Arquivo | Status |
|---|---|---|---|
| F-01 | `alertsDispatched` não incrementado em `CheckAlertsService` (cron path invisível para métricas) | `alerts/check-alerts.service.ts` | ✅ CORRIGIDO |
| F-02 | `marketplace: ''` hardcoded em notificações do cron — alerts sem nome de loja | `alerts/check-alerts.service.ts` | ✅ CORRIGIDO |
| F-03 | `TradingAnalyticsProcessor` sem Prometheus — sinais/regime/confidence invisíveis | `app/modules/trading/analytics/processor.py`, `api/metrics.py` | ✅ CORRIGIDO |

---

## Gaps Remanescentes (pós-Phase F)

| ID | Gap | Componente | Impacto | Prioridade |
|---|---|---|---|---|
| G-F-01 | `TradingBot` usa SQLite isolado — trades não visíveis no pipeline Postgres | TradingBot | Analytics de trades fora do data-core | Média |
| G-F-02 | `CryptoAnalyticsProcessor` (snapshot path) STUB — todos NULL | crypto-snapshot | Path secundário inativo | Média |
| G-F-03 | `LOG_JSON=true` não setado em produção (Coolify env var) | todos | Logs não estruturados em JSON | Baixa |
| G-F-04 | Zero usuários reais em poupi-baby — alertas nunca disparados em produção real | poupi-baby | KPI principal bloqueado | Alta |
| G-F-05 | `neighborhood_avg_price_m2` e `opportunity_score` NULL em real estate | real_estate | Analytics incompletas | Baixa |
| G-F-06 | Prometheus multi-process gap — pipeline_stage_* counters zerados no /metrics | todos | Requere Pushgateway | Média |
| G-F-07 | `TradingBot` sem Prometheus externo — métricas de trading só em SQLite | TradingBot | Visibilidade limitada | Média |
| G-F-08 | Sports odds inteiramente desativado — sem fonte real | sports_betting | Domínio inativo | Baixa |

---

## Critérios de Sucesso — Phase F

| Critério | Status |
|---|---|
| Trilha 1: alertsDispatched wired em ambos os paths (event + cron) | ✅ F-01 fix |
| Trilha 1: marketplace populado em notificações de cron | ✅ F-02 fix |
| Trilha 1: Watchlist flow auditado e funcional | ✅ dedup, soft delete, product check |
| Trilha 1: Notification processor auditado — BullMQ retry, template dispatch | ✅ sem gaps |
| Trilha 2: TradingAnalyticsProcessor com Prometheus (signal, regime, confidence) | ✅ F-03 fix |
| Trilha 2: TradingBot v4 auditado — MTF, trailing stop, autotune, MAE/MFE | ✅ L3 HARDENED |
| Trilha 2: Gaps remanescentes documentados sem bloqueio de produção | ✅ G-F-01 a G-F-08 |
| Maturity Matrix gerada | ✅ este documento |

---

*Gerado em Phase F — Internal Validation & Crypto Hardening*
