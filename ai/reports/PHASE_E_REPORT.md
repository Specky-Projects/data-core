# PHASE E REPORT — Data Validation and Operational Readiness

> Executed: 2026-05-16
> Scope: data-core platform + poupi-baby integration
> Phases completed: Fase 1–9

---

## Resumo Executivo

Phase E realizou auditoria profunda de todos os pipelines ativos (ecommerce, crypto, real_estate),
validou consistência raw→normalized→analytics, identificou e corrigiu 3 bugs e gerou a matriz
de readiness operacional. A plataforma está `READY_FOR_INTERNAL` para ecommerce e crypto OHLCV.

---

## Fase 1 — Auditoria de Dados Reais

### Descobertas por domínio

| Domínio | Dado real? | Verificação |
|---|---|---|
| Ecommerce | ✅ | 17 URLs VTEX ativas; EcommerceURLScraper → VTEX Catalog API + JSON-LD |
| Crypto OHLCV | ✅ | CryptoCoinOHLCVCollector → Binance real; DEFAULT_SYMBOLS = BTC/ETH/SOL/BNB/ADA |
| Real Estate | ✅ | ApolarCollector → Playwright real em apolar.com.br; Curitiba |
| Sports Odds | ❌ | Job desativado (Phase D); nenhuma fonte real configurada |
| Mock collectors | ✅ filtrados | schedulable=False em todos os 4 mocks (Phase D) |

---

## Fase 2 — Validação Raw → Normalized

### Pipeline ecommerce

```
EcommerceURLScraper
  → raw_collections (scrapedProduct v1.0.0, checksum dedup via stable_payload_hash)
    → PoupiLegacyScrapedProductV1Normalizer
      → normalized_products (canonical_product_id, title, price, store_name,
                              availability, source_url [pós-migration 0016])
        → analytics_status = pending → processed
```

**Rastreabilidade completa:** `normalizer_name`, `normalizer_version`, `normalized_at`,
`source_raw_schema_name`, `source_collector_name`, `DataLineage` via `LineageService`.

### Bug E-01 (CORRIGIDO)

**Antes:** `collection_raw_saved_total` definido em `api/metrics.py` mas nunca incrementado.
O contador ficava em 0 para todos os collectors, mesmo com coleta ativa.

**Causa raiz:** `workers/collector_worker.py` chamava `collector.save_raw()` mas não
importava nem incrementava a métrica.

**Fix:** Adicionado import de `collection_raw_saved_total` e `collection_raw_duplicates_total`;
ambos incrementados por item dentro do loop de coleta. `duplicate_raw_count` no metadata
do `CollectionRun` agora usa contador preciso em vez de `len(items) - raw_saved`.

```python
# workers/collector_worker.py — pós-fix
from api.metrics import collection_raw_duplicates_total, collection_raw_saved_total
...
item_saved = collector.save_raw(db, [item])
if item_saved:
    collection_raw_saved_total.labels(domain=domain_label, collector_name=metadata.name).inc(item_saved)
else:
    raw_duplicates += 1
    collection_raw_duplicates_total.labels(domain=domain_label, collector_name=metadata.name).inc()
```

### Bug E-03 (CORRIGIDO)

**Antes:** `NormalizedMarketCandle.__table_args__` declarava:
```python
Index("ix_norm_market_candle_identity", "source", "symbol", "timeframe", "timestamp")
```

Migration `0014_unique_market_candle_identity` criou `uq_norm_market_candle_identity` (UniqueConstraint)
no DB em substituição ao index. `CryptoSnapshotNormalizer` referenciava corretamente o nome
da constraint no `on_conflict_do_nothing()`, mas o model SQLAlchemy estava desatualizado.

**Impacto:** `create_all()` (usado em testes) não criaria a UniqueConstraint; descrepância
entre model e DB causava confusão no desenvolvimento.

**Fix:** Substituído `Index(...)` por `UniqueConstraint(..., name="uq_norm_market_candle_identity")`
no model, alinhando com a realidade do DB.

---

## Fase 3 — Validação de Analytics

### Crypto

**Caminho primário (ACTIVE_REAL_DATA):**
- `CryptoCoinOHLCVCollector` → OHLCV payload → `CryptoSnapshotNormalizer.save_normalized()` → `NormalizedMarketCandle`
- `TradingAnalyticsProcessor.calculate()` → `compute_indicators(df, cfg)` + `get_signal()`
- **Indicadores reais:** RSI(14), MA fast(9)/slow(21), ATR(14), ADX, volume_ratio, breakout_score, trend_score, signal (BUY/SELL/HOLD), confidence, regime

**Caminho secundário (STUB):**
- Snapshots não-OHLCV → `NormalizedCryptoSnapshot` → `CryptoAnalyticsProcessor`
- Retorna `volatility_24h=None`, `volume_spike_score=None`, `trend_score=None`, `regime=None`
- **Impacto:** O collector ativo (OHLCV) nunca produz snapshots, apenas candles. Path secundário está em standby.

### Ecommerce

`ProductPriceAnalyticsProcessor` — cálculos reais:
- `avg_price_7d`, `avg_price_30d`: média por `canonical_product_id` nos últimos N dias
- `min_price_90d`, `max_price_90d`: faixa histórica
- `price_score`: z-score clampeado a [-3,3] invertido → 0=caro, 1=barato

**Limitação:** Com canonical_product_id do tipo `slug:...`, a query agrupa por
título normalizado. Produtos com título levemente diferente entre stores podem
não ser agrupados. Impacto prático baixo para fraldas (títulos padronizados).

### Real Estate

`RealEstateAnalyticsProcessor`:
- `price_per_m2 = price / area_m2` — ✅ computado
- `neighborhood_avg_price_m2` — NULL (requer histórico agregado por bairro)
- `discount_vs_neighborhood` — NULL (depende de neighborhood_avg)
- `opportunity_score` — NULL (STUB explícito)

**Readiness:** PARTIAL — price_per_m2 correto; demais requerem histórico acumulado (semanas).

---

## Fase 4 — Histórico e Retenção

| Aspecto | Status |
|---|---|
| `data_retention_job` configurado | ✅ domingo 02:00 — 90d raw / 180d normalized / 60d runs |
| `NormalizedMarketCandle` dedup por UniqueConstraint | ✅ pós-fix E-03 (já estava no DB via migration 0014) |
| `NormalizedProduct.collected_at` indexado | ✅ + índice composto com canonical_product_id |
| `PriceHistory` em poupi-baby deduplicada | ✅ camada de serviço verifica mudança antes de criar |
| `pipeline_runs` preserva histórico de execução | ✅ `PipelineRecorder` em normalize_job e analytics_job |

---

## Fase 5 — Canonical Data Readiness

### NormalizedProduct — campos canônicos

| Campo | Presente | Populado | Fonte |
|---|---|---|---|
| `canonical_product_id` | ✅ | ✅ | EAN/UPC/GTIN > source_id > slug:title-sha1 |
| `source_url` | ✅ **NOVO** (migration 0016) | ✅ pós-fix E-04 | raw.target_url |
| `title` | ✅ | ✅ | scraper payload |
| `brand` | ✅ | ⚠️ quando disponível | scraper |
| `store_name` | ✅ | ✅ | source_name |
| `price` | ✅ | ✅ | scraper, parser robusto (R$/BRL/cents) |
| `availability` | ✅ | ✅ | scraper payload |
| `collected_at` | ✅ | ✅ | raw.collected_at |

---

## Fase 6 — Observabilidade Operacional

### Métricas Prometheus (data-core)

| Métrica | Status pós-Phase E | Observação |
|---|---|---|
| `collection_raw_saved_total` | ✅ WIRED | Fix E-01 |
| `collection_raw_duplicates_total` | ✅ WIRED | Fix E-01 |
| `pipeline_stage_runs_total` | ⚠️ 0 no /metrics | Multi-process gap* |
| `pipeline_stage_duration_seconds` | ⚠️ 0 no /metrics | Multi-process gap* |
| `pipeline_stage_last_success_timestamp` | ⚠️ 0 no /metrics | Multi-process gap* |
| `price_feed_requests_total` | ✅ | Incrementado no endpoint |
| `price_feed_items_served_total` | ✅ | Por store_name |
| `job_dead_letters_unresolved` | ✅ | Via set_function (DB query) |
| `circuit_breaker_open_sources` | ✅ | Via set_function (DB query) |
| `db_pool_size` / `db_pool_checked_out` | ✅ | Via set_function |

> *Multi-process gap: scheduler e worker são containers separados do API container. prom-client
> não compartilha estado entre processos. Solução: `pipeline_runs` DB table é o source of
> truth operacional. Pushgateway resolveria o gap mas está fora do escopo desta fase.

### Fonte primária de observabilidade: `pipeline_runs` table

Toda execução de normalize_job e analytics_job grava via `PipelineRecorder`:
- `domain`, `stage`, `trigger`, `status`, `started_at`, `finished_at`, `duration_seconds`
- `items_input`, `items_processed`, `items_skipped`, `items_error`
- `PipelineFailure` com traceback em caso de erro

---

## Fase 7 — Matriz de Readiness

**Arquivo gerado:** `docs/READINESS_MATRIX.md`
**Contexto IA:** `ai/contexts/readiness_status.md`

---

## Fase 8 — Correções Prioritárias

| Bug ID | Descrição | Arquivos | Status |
|---|---|---|---|
| E-01 | `collection_raw_saved_total` nunca incrementado | `workers/collector_worker.py` | ✅ CORRIGIDO |
| E-03 | `NormalizedMarketCandle` model declara Index em vez de UniqueConstraint | `app/normalization/models.py` | ✅ CORRIGIDO |
| E-04 | `source_url` ausente em NormalizedProduct e price_feed | `app/normalization/models.py`, `product_normalizer.py`, `poupi_baby_routes.py`, `alembic/versions/0016_*`, `data-core-sync.service.ts` | ✅ CORRIGIDO |

---

## Fase 9 — Validação Final

### Evidências de pipeline funcional

**Ecommerce (data-core):**
```
EcommerceURLScraper.collect_targets(17 targets)
  ✅ Strategy 1: VTEX /api/catalog_system/pub/products/search?fq=productId:{id}
  ✅ Strategy 2: JSON-LD fallback
  → raw_collections: scrapedProduct v1.0.0
  → PoupiLegacyScrapedProductV1Normalizer.run()
  → normalized_products: price, title, canonical_product_id, source_url (pós-0016)
  → ProductPriceAnalyticsProcessor.run()
  → product_price_analytics: avg7d, avg30d, min90d, max90d, price_score
  → /api/v1/poupi-baby/price-feed: 200 OK, items com source_url
```

**Crypto (data-core):**
```
CryptoCoinOHLCVCollector.collect()
  ✅ Binance CCXT: BTC/ETH/SOL/BNB/ADA × 15m, 1h
  → raw_collections: marketCandle v1.0.0
  → TradingCandleNormalizer.run()
  → normalized_market_candles: open/high/low/close/volume/timestamp (dedup UniqueConstraint)
  → TradingAnalyticsProcessor.run()
  → trading_analytics: rsi, ma_fast, ma_slow, atr, adx, signal, confidence, regime
  → /api/v1/analytics/signals (consumido por poupi-crypto)
```

**poupi-baby:**
```
DataCoreSyncService.syncPriceFeed() [cron 2h]
  → GET /api/v1/poupi-baby/price-feed
  → processItem() → updateOfferPrice() ou createProductAndOffer()
  ✅ source_url usado diretamente (pós-fix E-04)
  → OFFER_PRICE_UPDATED → AlertEventsListener
  → BullMQ notification queue → email/telegram
```

### Health checks

| Endpoint | Resposta esperada |
|---|---|
| `GET /live` | `{"status":"ok"}` |
| `GET /ready` | `{"status":"ok","postgres":"ok","redis":"ok"}` |
| `GET /health` | full dependency check |
| `GET /metrics` | Prometheus text format com `collection_raw_saved_total` > 0 pós-fix |
| `GET /api/v1/poupi-baby/price-feed` | `{"count":N,"items":[{..."source_url":"https://..."}]}` |

---

## Arquivos Alterados (Phase E)

| Arquivo | Tipo | Descrição |
|---|---|---|
| `workers/collector_worker.py` | Modified | Fix E-01: wire collection_raw_saved_total + duplicates counter |
| `app/normalization/models.py` | Modified | Fix E-03: UniqueConstraint para NormalizedMarketCandle; Fix E-04: campo source_url em NormalizedProduct |
| `app/modules/ecommerce/normalizers/product_normalizer.py` | Modified | Fix E-04: populate source_url from raw.target_url |
| `api/poupi_baby_routes.py` | Modified | Fix E-04: expõe source_url no price-feed |
| `alembic/versions/0016_normalized_product_source_url.py` | Created | Migração: ADD COLUMN source_url TEXT |
| `poupi-baby/backend/src/data-core-sync/data-core-sync.service.ts` | Modified | Fix E-04: usa source_url diretamente; backfill em updateOfferPrice |
| `docs/READINESS_MATRIX.md` | Created | Matriz de readiness por domínio |
| `ai/contexts/readiness_status.md` | Created | Contexto IA: readiness status |
| `ai/reports/PHASE_E_REPORT.md` | Created | Este relatório |

---

## Readiness Final

| Critério Phase E | Resultado |
|---|---|
| Todos os pipelines ativos possuem dados reais | ✅ Ecommerce, Crypto OHLCV, Real Estate |
| Raw e normalized consistentes | ✅ |
| Analytics funcionais | ✅ Ecommerce + Trading (Crypto); Real Estate PARTIAL |
| Histórico persistindo corretamente | ✅ |
| Observabilidade mínima existe | ✅ pipeline_runs + Prometheus (parcial) |
| Readiness operacional documentada | ✅ READINESS_MATRIX.md |
| Nenhum mock mascarando produção | ✅ |
| Pronta para testes internos reais | ✅ `READY_FOR_INTERNAL` |

---

*Phase E complete — Data Validation and Operational Readiness*
