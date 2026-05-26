# PHASE F REPORT — Internal Validation & Crypto Hardening

> Executed: 2026-05-16
> Scope: poupi-baby (Trilha 1) + data-core crypto domain (Trilha 2)
> Phases completed: Fase 1–10

---

## Resumo Executivo

Phase F executou duas trilhas paralelas de auditoria e hardening: validação interna
do poupi-baby (watchlist, alertas, Telegram, métricas) e auditoria profunda do
domínio crypto (TradingBot v4, TradingAnalyticsProcessor, MTF, indicadores, resiliência).

Foram identificados e corrigidos 3 bugs (F-01, F-02, F-03) e gerada a Maturity Matrix
com classificação por nível (L0–L4) para todos os componentes ativos.

**Resultado:** poupi-baby alert paths completamente observáveis; crypto pipeline com
Prometheus completo; TradingBot v4 classificado como `L3 — HARDENED`.

---

## Trilha 1 — Poupi Baby: Validação Interna

### Fase 1 — Watchlist Flow

**Auditoria de `AlertsService.watch/unwatch/myWatchlist`:**

| Critério | Status | Detalhe |
|---|---|---|
| Dedup ao adicionar | ✅ | `ON CONFLICT (user_id, product_id) DO UPDATE SET active = true, deleted_at = null` |
| Re-watch após unwatch | ✅ | Mesmo conflict restaura `active = true` e limpa `deleted_at` |
| Soft delete | ✅ | `active = false, deleted_at = now()` |
| Produto não encontrado | ✅ | `findUnique({ deletedAt: null })` antes de inserir |
| Listagem filtrada | ✅ | `active = true AND deleted_at IS NULL AND p.deleted_at IS NULL` |
| Auth guard | ✅ | `@UseGuards(AuthGuard('jwt'))` no controller |

**Rotas disponíveis:**
- `POST /alerts/watchlist/:productId` — adicionar (idempotente)
- `DELETE /alerts/watchlist/:productId` — remover (soft delete)
- `GET /alerts/watchlist` — listar produtos monitorados do usuário

### Fase 2 — Alert Flow

**AlertEventsListener (path primário event-driven):**
- ✅ `OFFER_PRICE_UPDATED` → `isHistoricalLowest()` via `priceHistory.aggregate._min.price`
- ✅ Tipo: `NEW_LOWEST_PRICE` ou `PRICE_DROP` (threshold 5%)
- ✅ Cooldown 24h via `UserEvent("smart_alert.TYPE")`
- ✅ `metrics.alertsDispatched.inc({ type, channel })` ← wired
- ✅ BullMQ routing — retry automático

**CheckAlertsService (path secundário cron 6h):**
- ✅ Batch de 100, paginado
- ✅ Cooldown via `UserEvent("alert.check_alerts_fired")`
- ✅ `previousPrice` lido da última `PriceHistory` (Phase C fix)
- ✅ BullMQ routing (`sendPriceAlert` + `sendSmartAlertTelegram`)
- ✅ **[F-01 fix]** `metrics.alertsDispatched.inc()` agora wired para email e telegram
- ✅ **[F-02 fix]** `marketplace` lido da relação Offer→Marketplace (era `''` hardcoded)

### Fase 3 — Telegram

**NotificationProcessor:**
- ✅ `alert.smart` → `telegram.sendSmartAlert()` com `chatId`, tipo, `productUrl`, preços, marketplace
- ✅ `sendSmartAlert()` usa HTML formatting: emoji, preço anterior riscado, link direto ao produto (source_url disponível desde E-04)
- ✅ `throw err` no `TelegramService` → BullMQ retry sem `try/catch` (Phase C fix)
- ✅ `notificationDelivered.inc({ channel: 'telegram', template, outcome: 'sent'/'failed' })`

### Fase 4 — Métricas

**Estado pós-Phase F:**

| Métrica | Path | Status |
|---|---|---|
| `alertsDispatched{type, channel}` | AlertEventsListener | ✅ wired (desde Phase C) |
| `alertsDispatched{type, channel}` | CheckAlertsService | ✅ **WIRED (F-01 fix)** |
| `notificationDelivered{channel, template, outcome}` | NotificationProcessor | ✅ wired |
| `syncItems{outcome}` | DataCoreSyncService | ✅ wired |
| `syncDuration` | DataCoreSyncService | ✅ wired |
| `bullQueueWaiting/Active/Failed` | MetricsService | ✅ wired |
| `httpRequestsTotal` + `httpRequestDuration` | HTTP layer | ✅ wired |

---

## Trilha 2 — Crypto Hardening

### Fase 5 — Auditoria do Domínio

**Pipeline data-core:**
```
CryptoCoinOHLCVCollector (Binance CCXT, 5 pares × 15m/1h)
  → raw_collections: marketCandle v1.0.0
    → TradingCandleNormalizer
      → normalized_market_candles (dedup UniqueConstraint uq_norm_market_candle_identity)
        → TradingAnalyticsProcessor
          → trading_analytics: RSI, MA, ATR, ADX, volume_ratio, breakout_score, signal, confidence, regime
          → Prometheus: trading_signal_total, trading_regime_total, trading_confidence_score [F-03]
```

**TradingBot v4 (sistema autônomo):**
- Paper trading por padrão (`paper_trading=True`)
- Binance via CCXT, configurável por `.env`
- Storage: SQLite próprio (`data/bot_storage.sqlite3`)
- 8 tabelas: `bot_runs`, `trade_results`, `market_snapshots`, `signal_decisions`, `entry_contexts`, `equity_points`, `shadow_trades`, `regime_records`

### Fase 6 — Melhorias Estruturais

| Funcionalidade | Implementação | Status |
|---|---|---|
| Multi-timeframe | `MultiTimeframeAnalyzer` — cache por TF, TTL = 1 candle | ✅ v4 |
| Trailing stop | `TrailingStop` — ativa com +1%, sobe com preço | ✅ v4 |
| Reconexão automática | `ReconnectionManager` — backoff exponencial | ✅ v4 |
| Position sizing dinâmico | `PositionSizer` — % do capital × confiança | ✅ v4 |
| State restore pós-restart | `_restore_open_position_state()` + reconciliação | ✅ v4 |
| Overtrading guard | `overtrading_decision()` — max trades/dia, cooldown, max losses | ✅ v4 |
| Regime entry decision | `regime_entry_decision()` — histórico de win rate por regime | ✅ v4 |
| Daily loss limit | `_daily_loss_breached()` — pausa até meia-noite | ✅ v4 |
| Weekly report | `send_weekly_report()` — toda segunda-feira via Telegram | ✅ v4 |
| Shadow trades | Trades paralelos sem execução real para comparação | ✅ v4 |
| Autotune semanal | `WeeklyScheduler` + `optimizer.py` — população/gerações via backtest | ✅ v4 |

### Fase 7 — Qualidade de Analytics

| Indicador | Cálculo | Validação |
|---|---|---|
| RSI(14) | `calc_rsi()` — pandas EWM | ✅ produz valores reais |
| MA fast(9) / slow(21) | SMA via rolling mean | ✅ crossover altista/baixista real |
| ATR(14), ATR% | `calc_atr()` — True Range | ✅ usado no trailing stop |
| ADX | `calc_adx()` — +DI/-DI | ✅ separação trending/ranging |
| Bollinger Bands | `calc_bollinger()` — 20 períodos, 2σ | ✅ modo RANGING |
| VWAP | `calc_vwap()` | ✅ calculado |
| Historical Volatility | `calc_hv()` | ✅ calculado |
| Breakout score | Composição ADX + volume + ATR | ✅ 0-100 |
| Confidence | Composição de 4-5 sinais validados | ✅ 0-100 |
| MAE / MFE | Position extremes tracking | ✅ salvo em `TradeResult` |
| Loss classification | `classify_loss()` — tipo de saída | ✅ slippage, fee, sinal |

### Fase 8 — Observabilidade Crypto

**Antes de Phase F:** `TradingAnalyticsProcessor` sem nenhuma métrica Prometheus.

**Fix F-03 — métricas adicionadas a `api/metrics.py`:**

```python
trading_signal_total      # Counter{symbol, timeframe, signal}
trading_regime_total      # Counter{symbol, timeframe, regime}
trading_confidence_score  # Histogram{symbol, timeframe} buckets=[0,10,...,100]
```

**Wired em `TradingAnalyticsProcessor.save_analytics()`** — métricas só disparam após
flush bem-sucedido no DB, garantindo consistência.

**Exemplo de queries Prometheus resultantes:**
```promql
# Distribuição de sinais por símbolo
rate(trading_signal_total{symbol="BTC/USDT"}[1h])

# Regime predominante nas últimas 4h
sum by (regime) (increase(trading_regime_total[4h]))

# Percentil 90 de confidence score
histogram_quantile(0.9, rate(trading_confidence_score_bucket[1h]))
```

---

## Arquivos Alterados (Phase F)

| Arquivo | Tipo | Descrição |
|---|---|---|
| `poupi-baby/backend/src/alerts/check-alerts.service.ts` | Modified | F-01: `alertsDispatched.inc()` wired; F-02: marketplace da relação DB |
| `data-core/api/metrics.py` | Modified | F-03: `trading_signal_total`, `trading_regime_total`, `trading_confidence_score` |
| `data-core/app/modules/trading/analytics/processor.py` | Modified | F-03: import + wiring das métricas em `save_analytics()` |
| `data-core/docs/MATURITY_MATRIX.md` | Created | Matriz de maturidade por componente e dimensão |
| `data-core/ai/contexts/maturity_status.md` | Created | Contexto IA: maturidade atual |
| `poupi-baby/ai/base/reuse_and_dedup_rules.md` | Created | Regras de anti-duplicação e padrões consolidados |
| `data-core/ai/reports/PHASE_F_REPORT.md` | Created | Este relatório |

---

## Fase 9 — Maturity Matrix

**Arquivo gerado:** `docs/MATURITY_MATRIX.md`
**Contexto IA:** `ai/contexts/maturity_status.md`

Classificações finais:

| Componente | Maturidade |
|---|---|
| TradingBot v4 | `L3 — HARDENED` |
| Ecommerce pipeline | `L2 — OBSERVABLE` |
| Crypto OHLCV pipeline | `L2 — OBSERVABLE` |
| poupi-baby alerts | `L2 — OBSERVABLE` |
| poupi-baby sync | `L2 — OBSERVABLE` |
| Real Estate pipeline | `L1 — FUNCTIONAL` |
| Sports Odds | `L0 — NOT_READY` |

---

## Fase 10 — Validação Final

### Evidências de pipeline funcional (pós-Phase F)

**Alert path completo (event-driven):**
```
OFFER_PRICE_UPDATED event
  → AlertEventsListener.handleOfferPriceUpdated()
  → isHistoricalLowest() → tipo: NEW_LOWEST_PRICE / PRICE_DROP
  → cooldown check (UserEvent 24h)
  → NotificationQueueService.sendSmartAlert() + sendSmartAlertTelegram()
  → metrics.alertsDispatched.inc({ type, channel }) ← wired
  → NotificationProcessor → email + Telegram
  → metrics.notificationDelivered.inc({ channel, template, outcome })
```

**Alert path completo (cron fallback):**
```
@Cron('0 0 2-23/6 * * *') → CheckAlertsService.checkAlerts()
  → batch de 100 alertas ativos
  → lowestPrice ≤ targetPrice → cooldown check
  → previousPrice da PriceHistory
  → NotificationQueueService.sendPriceAlert() [marketplace=real]
  → metrics.alertsDispatched.inc({ type: 'PRICE_DROP', channel: 'email' }) ← NOVO (F-01)
  → sendSmartAlertTelegram() se telegramChatId
  → metrics.alertsDispatched.inc({ type: 'PRICE_DROP', channel: 'telegram' }) ← NOVO (F-01)
  → markSent() → UserEvent cooldown
```

**Trading analytics com Prometheus:**
```
TradingAnalyticsProcessor.save_analytics()
  → trading_analytics row persistida no Postgres
  → trading_signal_total{symbol, timeframe, signal}.inc() ← NOVO (F-03)
  → trading_regime_total{symbol, timeframe, regime}.inc() ← NOVO (F-03)
  → trading_confidence_score{symbol, timeframe}.observe(confidence) ← NOVO (F-03)
```

---

## Readiness Final

| Critério Phase F | Resultado |
|---|---|
| Watchlist flow auditado e funcional | ✅ |
| Ambos os paths de alerta observáveis via Prometheus | ✅ |
| Telegram template com source_url e marketplace real | ✅ |
| Trading analytics com métricas Prometheus completas | ✅ |
| TradingBot v4 auditado — resiliente e hardened | ✅ |
| Nenhum gap novo criado — apenas fixes e documentação | ✅ |
| Maturity Matrix gerada | ✅ |
| reuse_and_dedup_rules.md criado | ✅ |

---

*Phase F complete — Internal Validation & Crypto Hardening*
