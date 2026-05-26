# PHASE G REPORT — Product Validation & Crypto Research Layer

> Executed: 2026-05-16
> Scope: poupi-baby (Trilha A) + data-core crypto research (Trilha B)
> Fases: 1–12

---

## Resumo Executivo

Phase G executou duas trilhas paralelas com foco em validação de produto interno
e maturidade quantitativa do domínio crypto. Foram implementados 13 artefatos
novos ou complementares, respeitando a regra de reaproveitamento: nenhum pipeline,
fila, modelo ou serviço existente foi duplicado.

**Trilha A**: CTR tracking, opportunity engine exposto, watchlist observabilidade.
**Trilha B**: OHLCV integrity checker, DB replay offline, Sortino/Calmar, 5 novas métricas Prometheus.

**Crypto classificado**: `L3 — Research Engine` (dados + analytics + replay + observabilidade).
**poupi-baby classificado**: `L2 — Observable` (produto funcional + observabilidade básica).

---

## Auditoria Pre-Implementation (Anti-Duplicação)

Antes de criar qualquer artefato, verificado o que já existia:

| Item auditado | Resultado | Decisão |
|---|---|---|
| DealScoreService.calculate() | ✅ Existe e é completo | Complementar com `getTopOpportunities()` |
| DealScoreController | ✅ Existe com 2 endpoints | Adicionar `GET /opportunities` |
| analytics/metrics/calc.py (sharpe, drawdown, expectancy) | ✅ Existe | Complementar com sortino, calmar, exposure |
| backtest_runner.py (backtest CLI) | ✅ Existe | Criar `db_replay.py` separado — não contaminar o runner |
| simulation.py (paper_process_candle) | ✅ Existe e é reutilizável | `db_replay.py` importa e reutiliza |
| MetricsService | ✅ Existe com 8 métricas | Adicionar notificationEngaged, watchlistActions |
| UserEvent table | ✅ Existe (cooldown, analytics) | Reutilizar para tracking events |
| NotificationsModule | ✅ Existe | Adicionar tracking controller/service |
| AlertsService.watch/unwatch | ✅ Existe | Adicionar metrics.watchlistActions.inc() |

---

## TRILHA A — POUPI BABY

### Fase 1 — Validação Interna Controlada

**Status**: Infraestrutura completa. Pendente: seed de usuários internos.

O ambiente para validação interna já estava completo desde Phase C/E/F:
- Telegram bot operacional
- BullMQ + retry
- AlertEventsListener + CheckAlertsService
- price-feed com source_url para links diretos

**Ação recomendada pós-Phase G**: Criar 2-3 contas de teste com `telegramChatId`
configurado e adicionar à watchlist produtos Pampers/fraldas.

### Fase 2 — Watchlists Reais

**Auditado**: Fluxo já completo desde Phase E/F.

| Critério | Status |
|---|---|
| Dedup ON CONFLICT | ✅ |
| Soft delete | ✅ |
| Re-watch restaura active=true | ✅ |
| Product existence check | ✅ |
| source_url em links | ✅ pós-E-04 |
| Auth guard JWT | ✅ |

### Fase 3 — Tracking e Métricas (CTR)

**Implementado:**

**`MetricsService` — novas métricas:**
```ts
// poupi_notification_engaged_total{channel, type, template}
notificationEngaged: Counter   // opened | clicked por canal e template

// poupi_watchlist_actions_total{action}
watchlistActions: Counter       // created | removed
```

**`NotificationTrackingService`** — `GET /notifications/track`:
- Token opaco base64url: `userId:productId:template:channel:issuedAt`
- TTL: 7 dias
- Falha silenciosa (nunca quebra UX de email)
- `type=opened` → retorna pixel GIF 1x1 transparente
- `type=clicked` → redirect 302 para URL do produto
- Persiste `UserEvent(eventType: 'notification.opened' | 'notification.clicked')`
- Incrementa `metrics.notificationEngaged.inc({ channel, type, template })`

**`AlertsService`** — watchlist tracking:
- `watch()` → `metrics.watchlistActions.inc({ action: 'created' })`
- `unwatch()` → `metrics.watchlistActions.inc({ action: 'removed' })`

**Queries Prometheus:**
```promql
# CTR de alertas por template nas últimas 24h
rate(poupi_notification_engaged_total{type="clicked"}[24h])
  / rate(poupi_notification_delivered_total{outcome="sent"}[24h])

# Watchlists ativas (total criadas - removidas)
poupi_watchlist_actions_total{action="created"}
  - poupi_watchlist_actions_total{action="removed"}
```

### Fase 4 — Opportunity Engine

**Complementado** `DealScoreService.getTopOpportunities()`:
- Query SQL: `offers` com `COUNT(price_history) >= 3` (histórico mínimo para score)
- Filtra por `minScore` (padrão 60)
- Ordena por `score DESC`
- Retorna até `limit` resultados (máx 50)

**Endpoint:** `GET /deal-score/opportunities?limit=20&minScore=60`

```json
[
  {
    "productId":    "uuid",
    "productSlug":  "pampers-premium-care-g-26un",
    "productName":  "Pampers Premium Care G 26un",
    "offerId":      "uuid",
    "marketplace":  "Drogasil",
    "currentPrice": 54.90,
    "productUrl":   "https://www.drogasil.com.br/...",
    "score": {
      "score": 78,
      "label": "Ótima oferta",
      "emoji": "⚡",
      "components": { "historicalDiscount": 24, "nearAllTimeLow": 18, ... },
      "context": { "avg90d": 71.50, "discountVsAvg": -23.2, ... }
    }
  }
]
```

### Fase 5 — Canonical Products

**Auditado**: Camada canônica já existente e funcional.

| Critério | Status | Implementação |
|---|---|---|
| Deduplicação por slug | ✅ | `Product.slug UNIQUE`, upsert |
| Aliases/canonical name | ✅ | `Product.canonicalName` |
| Categoria consistente | ✅ | `Product.category` |
| Marca consistente | ✅ | `Product.brand` |
| `canonical_product_id` em data-core | ✅ | EAN > UPC > GTIN > source_id > slug:sha1 |
| Normalização de seller | ✅ | `Marketplace.slug UNIQUE` |
| Cross-marketplace dedup | ✅ | Um `Product` para múltiplos `Offer`s |

---

## TRILHA B — CRYPTO RESEARCH LAYER

### Fase 6 — Auditoria da Research Layer

**Inventário completo do que existe:**

| Componente | Status | Localização |
|---|---|---|
| `TradingBot v4` | ✅ HARDENED | `core/engine/trading_engine.py` |
| `TradingAnalyticsProcessor` | ✅ REAL (Prometheus F-03) | `app/modules/trading/analytics/processor.py` |
| `simulation.py` | ✅ Realista + bar+1 + intracandle SL/TP | `backtesting/simulation.py` |
| `backtest_runner.py` | ✅ walk-forward, compare, realistic | `backtest_runner.py` |
| `calc.py` (métricas) | ✅ sharpe, drawdown, expectancy | `analytics/metrics/calc.py` |
| `StorageRepository` | ✅ 20+ métodos | `data/storage/repository.py` |
| `MultiTimeframeAnalyzer` | ✅ cache, TTL, BULLISH/BEARISH/NEUTRAL | `indicators/mtf.py` |
| `autotune/optimizer.py` | ✅ genético, população/gerações | `autotune/optimizer.py` |
| `WeeklyScheduler` | ✅ autotune semanal | `autotune/scheduler.py` |

**Gap principal detectado:** `backtest_runner.py` sempre busca dados do Binance
online — sem possibilidade de replay 100% offline com dados históricos já coletados.

### Fase 7 — Backtesting e Replay

**Criado `domains/crypto_coin/backtesting/db_replay.py`:**

```
Fontes de dados para backtest:
  backtest_runner.py   → Binance API (online, ~90 dias)
  db_replay.py [NOVO]  → normalized_market_candles no Postgres (offline, reproduzível)
```

**Separação clara de responsabilidades:**
```
simulation.py           ← motor compartilhado (paper_process_candle)
    ↑ reutilizado por
backtest_runner.py      ← dados online (Binance)
db_replay.py            ← dados offline (Postgres normalized_market_candles)
```

**`replay_from_db(db, symbol, timeframe, days, realistic=True)`:**
- Carrega candles de `normalized_market_candles` (sem rede)
- Reutiliza `paper_process_candle()` e `paper_finalize_open_position()`
- Retorna métricas completas: sharpe, **sortino**, **calmar**, drawdown, expectancy, profit_factor, B&H

**CLI:**
```bash
python -m domains.crypto_coin.backtesting.db_replay --symbol BTC/USDT --tf 15m --days 90
python -m domains.crypto_coin.backtesting.db_replay --all-symbols --days 30 --json
```

### Fase 8 — Dataset Histórico

**Criado `domains/crypto_coin/analytics/ohlcv_integrity.py`:**

Detecções implementadas:
| Tipo | Threshold | Saída |
|---|---|---|
| Gap temporal | delta > 1.5× tf_seconds | `GapRecord` com missing_candles |
| Timestamp duplicado | hash set por candle | `AnomalyRecord(kind='duplicate')` |
| OHLC inválido | high < low (± 0.1%) | `AnomalyRecord(kind='ohlc_invalid')` |
| Close fora do range | close > high ou < low | `AnomalyRecord(kind='ohlc_invalid')` |
| Volume zero | volume == 0.0 | `AnomalyRecord(kind='zero_volume')` |
| Price spike | variação close→close > 20% | `AnomalyRecord(kind='price_spike')` |

**Status:**
- `CLEAN`: completeness ≥ 99% e 0 anomalias
- `ACCEPTABLE`: ≥ 95% e ≤ 5 anomalias
- `DEGRADED`: ≥ 85%
- `CRITICAL`: < 85%

**CLI:**
```bash
python -m domains.crypto_coin.analytics.ohlcv_integrity --symbol BTC/USDT --tf 15m
python -m domains.crypto_coin.analytics.ohlcv_integrity --all --days 30 --json
```

### Fase 9 — Portfolio Analytics

**Complementado `analytics/metrics/calc.py`:**

| Função | Nova? | Descrição |
|---|---|---|
| `sharpe_ratio()` | Existia | Retorno/std por trade |
| `sortino_ratio()` | **NOVA** | Retorno/downside std (penaliza só trades negativos) |
| `calmar_ratio()` | **NOVA** | Total return / max drawdown |
| `exposure_pct()` | **NOVA** | % de candles em posição |
| `max_drawdown()` | Existia | Queda máxima pico→vale |
| `expectancy()` | Existia | Retorno médio por trade |
| `profit_factor()` | Existia | Lucro bruto / perda bruta |

**`compute_all()` expandido** agora retorna:
```python
{
    "sharpe":           ...,
    "sortino":          ...,    # NOVO
    "calmar":           ...,    # NOVO
    "max_drawdown":     ...,
    "expectancy":       ...,
    "profit_factor":    ...,
    "avg_win":          ...,
    "avg_loss":         ...,
    "total_trades":     ...,
    "win_count":        ...,    # NOVO
    "loss_count":       ...,    # NOVO
    "total_return_pct": ...,    # NOVO
}
```

### Fase 10 — Observabilidade Crypto

**5 novas métricas em `api/metrics.py`:**

```python
backtest_runs_total               # Counter{symbol, timeframe, mode}
backtest_duration_seconds         # Histogram{symbol, timeframe, mode}
backtest_candles_processed_total  # Counter{symbol, timeframe}
ohlcv_integrity_checks_total      # Counter{symbol, timeframe, status}
ohlcv_gaps_detected_total         # Counter{symbol, timeframe}
```

**Wire pendente**: `backtest_runs_total` e `ohlcv_integrity_checks_total` precisam
ser incrementados nos respectivos runners (CLI ou chamada programática).
Documentados em `G-H-05` e `G-H-04`.

### Fase 11 — Evolution Matrix

**Arquivo gerado**: `docs/EVOLUTION_MATRIX.md`
**Contexto IA**: `ai/contexts/evolution_status.md`

---

## Arquivos Alterados (Phase G)

### Trilha A — Poupi Baby

| Arquivo | Tipo | Descrição |
|---|---|---|
| `metrics/metrics.service.ts` | Modified | notificationEngaged + watchlistActions counters |
| `alerts/alerts.service.ts` | Modified | Inject MetricsService; watchlistActions.inc() em watch/unwatch |
| `deal-score/deal-score.service.ts` | Modified | getTopOpportunities() — query SQL + score filter |
| `deal-score/deal-score.controller.ts` | Modified | GET /deal-score/opportunities |
| `notifications/notifications.module.ts` | Modified | Registro de TrackingController/Service |
| `notifications/tracking/notification-tracking.controller.ts` | Created | GET /notifications/track |
| `notifications/tracking/notification-tracking.service.ts` | Created | Token + UserEvent + metrics |

### Trilha B — Crypto

| Arquivo | Tipo | Descrição |
|---|---|---|
| `domains/crypto_coin/analytics/metrics/calc.py` | Modified | sortino_ratio, calmar_ratio, exposure_pct; compute_all expandido |
| `domains/crypto_coin/analytics/ohlcv_integrity.py` | Created | OHLCV integrity checker completo |
| `domains/crypto_coin/backtesting/db_replay.py` | Created | Replay offline de normalized_market_candles |
| `data-core/api/metrics.py` | Modified | 5 métricas de backtest + OHLCV integrity |

### Documentação

| Arquivo | Tipo | Descrição |
|---|---|---|
| `data-core/docs/EVOLUTION_MATRIX.md` | Created | Matriz de evolução L0-L4 por domínio e dimensão |
| `data-core/ai/contexts/evolution_status.md` | Created | Contexto IA: status de evolução |
| `data-core/ai/reports/PHASE_G_REPORT.md` | Created | Este relatório |

---

## Fase 12 — Validação Final

### Poupi Baby — evidências

| Componente | Evidência |
|---|---|
| GET /deal-score/opportunities | Endpoint funcional; filtra por score ≥ 60; retorna top 20 por padrão |
| GET /notifications/track?type=opened | Retorna pixel GIF 1x1 + registra UserEvent |
| GET /notifications/track?type=clicked&redirect=URL | Redirect 302 + registra UserEvent |
| poupi_notification_engaged_total | Counter wired para tipo opened/clicked por canal+template |
| poupi_watchlist_actions_total | Counter wired em watch() e unwatch() |
| DealScore 5 componentes | historicalDiscount, nearAllTimeLow, stability, recentTrend, promoRarity |
| Canonical products | Auditados — funcional, dedup por slug, cross-marketplace |

### Crypto — evidências

| Componente | Evidência |
|---|---|
| db_replay.py | `replay_from_db(db, "BTC/USDT", "15m", days=90)` → dict completo com sharpe/sortino |
| ohlcv_integrity.py | `check_integrity(db, "BTC/USDT", "15m")` → OHLCVIntegrityReport com status |
| sortino_ratio() | Calculado em `compute_all()` — penaliza downside, não total volatilidade |
| calmar_ratio() | Calculado em `compute_all()` — total_return / max_drawdown |
| 5 novas métricas Prometheus | Definidas em api/metrics.py, prontas para wirear nos runners |

---

## Critérios de Sucesso

| Critério | Status |
|---|---|
| Trilha A: CTR tracking funcional (endpoint + UserEvent + métrica) | ✅ |
| Trilha A: Watchlist actions rastreáveis via Prometheus | ✅ |
| Trilha A: Opportunity engine exposto com endpoint autenticado | ✅ |
| Trilha A: Canonical products auditados — sem gaps críticos | ✅ |
| Trilha B: Replay desacoplado (db_replay.py offline, sem Binance) | ✅ |
| Trilha B: Analytics fortalecidos (sortino, calmar, exposure) | ✅ |
| Trilha B: OHLCV integrity checker completo (gaps, anomalias, duplicatas) | ✅ |
| Trilha B: 5 novas métricas Prometheus para backtest/OHLCV | ✅ |
| Evolution Matrix criada | ✅ |
| SEM onboarding público de crypto | ✅ |
| SEM usuários reais (aguarda ação de aquisição) | ✅ (documentado G-H-01) |

---

*Phase G complete — Product Validation & Crypto Research Layer*
