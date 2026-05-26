# READINESS MATRIX — Poupi Platform

> Generated: 2026-05-16 | Phase E — Data Validation and Operational Readiness
>
> Classifica cada domínio ativo contra os critérios mínimos de readiness operacional
> para testes internos reais.

---

## Legenda de Readiness

| Status | Critério |
|---|---|
| `READY_FOR_USERS` | Todos os critérios atendidos; apto para usuários reais |
| `READY_FOR_INTERNAL` | Dados reais, pipeline funcional; gaps menores não-bloqueantes |
| `PARTIAL` | Pipeline parcialmente funcional; gaps ativos impactam experiência |
| `NOT_READY` | Sem dados reais ou pipeline quebrado |

---

## Matriz Principal

| Domínio | Coleta Real | Raw | Normalized | Analytics | Histórico | Observabilidade | Readiness |
|---|---|---|---|---|---|---|---|
| **Ecommerce** | ✅ 17 targets VTEX | ✅ `scrapedProduct v1.0.0` | ✅ `normalized_products` | ✅ avg7d/30d, min/max90d, price_score | ✅ `collected_at` indexado | ⚠️ metrics pós-fix E-01 | `READY_FOR_INTERNAL` |
| **Crypto (OHLCV)** | ✅ Binance 5 pares × 2 TF | ✅ `marketCandle v1.0.0` | ✅ `normalized_market_candles` | ✅ RSI/MA/ATR/ADX/signal via TradingAnalyticsProcessor | ✅ UniqueConstraint dedup | ⚠️ metrics pós-fix E-01 | `READY_FOR_INTERNAL` |
| **Crypto (snapshot)** | ✅ OHLCV → snapshot path | ✅ `marketCandle v1.0.0` | ✅ `normalized_crypto_snapshots` | ⚠️ STUB — CryptoAnalyticsProcessor retorna NULL | ✅ `collected_at` | ⚠️ parcial | `PARTIAL` |
| **Real Estate** | ✅ Playwright Apolar | ✅ `realEstateHtmlPage` | ✅ `normalized_real_estate_listings` | ⚠️ PARTIAL — price_per_m2 ok; neighborhood/opportunity NULL | ✅ `collected_at` | ⚠️ parcial | `PARTIAL` |
| **Sports Odds** | ❌ Desativado | ❌ | ❌ | ❌ | ❌ | ❌ | `NOT_READY` |
| **poupi-baby sync** | ✅ price-feed 2h | ✅ Offers upsertadas | ✅ Products canonicalizados | ✅ DealScore + AlertEventsListener | ✅ PriceHistory | ✅ BullMQ + Prometheus | `READY_FOR_INTERNAL` |

---

## Detalhe por Critério

### Coleta Real

| Domínio | Fonte | Frequência | Targets | Mock? |
|---|---|---|---|---|
| Ecommerce | Drogasil, Drogaraia, Pague Menos (VTEX) | 2h | 17 URLs | ❌ |
| Crypto OHLCV | Binance via CCXT | 15 min | BTC/ETH/SOL/BNB/ADA × 15m,1h | ❌ |
| Real Estate | apolar.com.br via Playwright | Diário 03:30 | max 25 listings | ❌ |
| Sports Odds | — | — | — | N/A |

### Raw → Normalized (pipeline consistency)

| Domínio | Normalizer | Schema | processing_status | Rastreabilidade | Dedup |
|---|---|---|---|---|---|
| Ecommerce | `PoupiLegacyScrapedProductV1Normalizer` | `scrapedProduct v1.0.0` | ✅ normalized/ignored/failed | ✅ normalizer_name, collected_at, source_* | checksum via `stable_payload_hash` |
| Crypto | `CryptoSnapshotNormalizer` / `TradingCandleNormalizer` | `marketCandle v1.0.0` | ✅ | ✅ | ✅ `uq_norm_market_candle_identity` (migration 0014) |
| Real Estate | `RealEstateListingNormalizer` | `realEstateHtmlPage` | ✅ | ✅ | por URL |
| Sports Odds | `SportsOddsNormalizer` | N/A | N/A | N/A | N/A |

### Analytics

| Domínio | Processor | Indicadores | Status |
|---|---|---|---|
| Ecommerce | `ProductPriceAnalyticsProcessor` | avg_7d, avg_30d, min_90d, max_90d, price_score (z-score) | ✅ REAL |
| Crypto OHLCV | `TradingAnalyticsProcessor` | RSI, MA fast/slow, ATR, ADX, volume_ratio, breakout_score, signal, confidence, regime | ✅ REAL |
| Crypto Snapshot | `CryptoAnalyticsProcessor` | volatility_24h, volume_spike_score, trend_score, regime | ⚠️ STUB — todos NULL |
| Real Estate | `RealEstateAnalyticsProcessor` | price_per_m2 ✅ / neighborhood_avg NULL / opportunity_score NULL | ⚠️ PARTIAL |
| Sports Odds | `SportsOddsAnalyticsProcessor` | line_movement, CLV, EV | ⚠️ STUB — sem dados |
| Trading | `TradingAnalyticsProcessor` | (mesma que Crypto OHLCV) | ✅ REAL |

### Histórico e Retenção

| Domínio | Campo | Retenção | Histórico válido? |
|---|---|---|---|
| Ecommerce | `collected_at` em NormalizedProduct | 90 dias (raw) / 180 dias (normalized) | ✅ |
| Crypto | `timestamp` em NormalizedMarketCandle | 90 dias (raw) | ✅ |
| Real Estate | `collected_at` em NormalizedRealEstateListing | 90 dias | ✅ |
| poupi-baby | `capturedAt` em PriceHistory | ilimitado (soft) | ✅ |

### Canonical Data (Phase E Fase 5)

| Campo | NormalizedProduct | Populado? | Fonte |
|---|---|---|---|
| `canonical_product_id` | ✅ | ✅ EAN/UPC/GTIN > source_id > title_slug | normalizer |
| `source_url` | ✅ (migration 0016) | ✅ pós-fix E-04 | raw.target_url |
| `title` | ✅ | ✅ | scraper payload |
| `brand` | ✅ | ⚠️ presente quando scraper extrai | scraper payload |
| `store_name` | ✅ | ✅ | source_name |
| `price` | ✅ | ✅ | scraper payload |
| `availability` | ✅ | ✅ | scraper payload |
| `collected_at` | ✅ | ✅ | raw.collected_at |

### Observabilidade

| Componente | Prometheus | PipelineRuns DB | Logs estruturados | Health check |
|---|---|---|---|---|
| data-core API | ✅ `/metrics` | N/A | ⚠️ LOG_JSON não ativado em prod | ✅ /live /ready /health |
| Scheduler jobs | ⚠️ multi-process gap* | ✅ pipeline_runs table | ✅ Phase D Fase 5 | N/A |
| Worker (normalize/analytics) | ⚠️ multi-process gap* | ✅ pipeline_runs table | ✅ PipelineRecorder | N/A |
| poupi-baby backend | ✅ :3001/metrics | N/A | ✅ NestJS Logger | ✅ /healthz |
| poupi-baby worker | ✅ :3002/metrics | N/A | ✅ NestJS Logger | ✅ :3002/healthz |
| `collection_raw_saved_total` | ✅ pós-fix E-01 | N/A | N/A | N/A |

> *Multi-process gap: prom-client é in-process; scheduler/worker atualizam contadores em processos separados do API. Contadores de pipeline são 0 no /metrics mas corretos na tabela `pipeline_runs`. Solução completa requer Pushgateway.

---

## Gaps Remanescentes (pós-Phase E)

| ID | Gap | Domínio | Impacto | Prioridade |
|---|---|---|---|---|
| G-E-01 | `CryptoAnalyticsProcessor` retorna tudo NULL | crypto-snapshot | Analytics vazias para snapshots; path primário (OHLCV/trading) não afetado | Média |
| G-E-02 | `RealEstateAnalyticsProcessor` — neighborhood_avg, opportunity_score NULL | real_estate | Analytics de imóvel incompletas | Baixa (falta histórico suficiente) |
| G-E-03 | `source_url` NULL em registros antes de migration 0016 | ecommerce | Links quebrados em offers antigas | Baixa (novo scraping popula) |
| G-E-04 | Prometheus multi-process gap | todos | Métricas pipeline zeradas no /metrics | Média (Pushgateway como solução) |
| G-E-05 | `LOG_JSON=true` não setado em produção | todos | Logs não estruturados em JSON | Baixa (env var simples) |
| G-E-06 | Sports odds sem fonte real | sports_betting | Domínio inteiro inativo | Baixa (aguarda integração) |
| G-E-07 | Zero usuários reais em poupi-baby | poupi-baby | Alertas nunca disparados em produção | Alta (ação de aquisição) |

---

## Critérios de Sucesso — Resultado Final

| Critério | Status |
|---|---|
| Pipelines ativos possuem dados reais | ✅ Ecommerce, Crypto, Real Estate |
| Raw e normalized consistentes | ✅ Pipeline estável; rastreabilidade completa |
| Analytics funcionais | ✅ Ecommerce (price_score) + Trading (RSI/MA/ATR/signal) |
| Histórico persistindo corretamente | ✅ Timestamps indexados, dedup ativo |
| Observabilidade mínima existe | ✅ pipeline_runs + Prometheus parcial + logs estruturados |
| Readiness operacional documentada | ✅ Esta matriz |
| Nenhum mock mascarando produção | ✅ schedulable=False em todos os mocks (Phase D) |
| Pronta para testes internos reais | ✅ Ecommerce + Crypto: `READY_FOR_INTERNAL` |

---

*Gerado em Phase E — Data Validation and Operational Readiness*
