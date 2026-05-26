# Maturity Status — Poupi Platform

> Last updated: 2026-05-16 (Phase F — Internal Validation & Crypto Hardening)
> Full detail: `docs/MATURITY_MATRIX.md`

## Maturidade por Componente

| Componente | Nível | Notas |
|---|---|---|
| Ecommerce pipeline | `L2 — OBSERVABLE` | Prometheus wired (E-01), pipeline_runs, source_url (E-04) |
| Crypto OHLCV pipeline | `L2 — OBSERVABLE` | trading_signal/regime/confidence metrics (F-03) |
| TradingBot v4 | `L3 — HARDENED` | MTF, trailing stop, state restore, autotune, shadow trades |
| Real Estate pipeline | `L1 — FUNCTIONAL` | Analytics parcial; sem métricas específicas |
| poupi-baby sync | `L2 — OBSERVABLE` | BullMQ, MetricsService, upsert dedup |
| poupi-baby alerts (event) | `L2 — OBSERVABLE` | AlertEventsListener, cooldown, alertsDispatched |
| poupi-baby alerts (cron) | `L2 — OBSERVABLE` | CheckAlertsService F-01 fix, marketplace F-02 fix |
| Sports Odds | `L0 — NOT_READY` | Domínio desativado |

## Bugs Corrigidos em Phase F

| ID | Descrição | Arquivo |
|---|---|---|
| F-01 | `alertsDispatched` não incrementado em `CheckAlertsService` — cron path invisível | `alerts/check-alerts.service.ts` |
| F-02 | `marketplace: ''` hardcoded em notificações do cron | `alerts/check-alerts.service.ts` |
| F-03 | `TradingAnalyticsProcessor` sem Prometheus para sinais, regime, confidence | `app/modules/trading/analytics/processor.py`, `api/metrics.py` |

## Gaps Prioritários Remanescentes

- **G-F-04 (Alta)**: Zero usuários reais em poupi-baby — ação de aquisição necessária
- **G-F-06 (Média)**: Prometheus multi-process gap — usar pipeline_runs como source of truth
- **G-F-01 (Média)**: TradingBot usa SQLite isolado — trades fora do pipeline Postgres
- **G-F-07 (Média)**: TradingBot sem Prometheus externo

## O que está PRONTO para testes internos

- Alertas de queda de preço: ambos os paths (event-driven + cron) com métricas completas
- Trading analytics: signal, regime, confidence visíveis no Prometheus
- Watchlist: CRUD funcional com dedup e soft delete
- Notificações Telegram: template alert.smart com source_url (link direto ao produto)
- TradingBot: paper trading com todas as proteções ativas (MTF, trailing, autotune)
