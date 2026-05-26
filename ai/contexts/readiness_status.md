# Readiness Status — data-core platform

> Last updated: 2026-05-16 (Phase E — Data Validation and Operational Readiness)
> Full detail: `docs/READINESS_MATRIX.md`

## Readiness por Domínio

| Domínio | Readiness | Notas |
|---|---|---|
| Ecommerce | `READY_FOR_INTERNAL` | 17 targets VTEX ativos; price analytics real; source_url fix aplicado |
| Crypto OHLCV | `READY_FOR_INTERNAL` | Binance real; TradingAnalytics com RSI/MA/ATR/signal |
| Crypto Snapshot | `PARTIAL` | CryptoAnalyticsProcessor STUB (todos NULL) |
| Real Estate | `PARTIAL` | Apolar operacional; analytics partial (neighborhood NULL) |
| Sports Odds | `NOT_READY` | Job desativado; sem fonte real |
| poupi-baby (consumer) | `READY_FOR_INTERNAL` | Sync ativo; alerts configurados; falta usuário real |

## Bugs Corrigidos nesta Fase

| ID | Descrição | Arquivo |
|---|---|---|
| E-01 | `collection_raw_saved_total` nunca incrementado | `workers/collector_worker.py` |
| E-03 | `NormalizedMarketCandle.__table_args__` declarava `Index` em vez de `UniqueConstraint` | `app/normalization/models.py` |
| E-04 | `price_feed` não expunha `source_url`; poupi-baby não conseguia montar links de produto | `api/poupi_baby_routes.py`, `app/normalization/models.py`, `app/modules/ecommerce/normalizers/product_normalizer.py`, `alembic/versions/0016_*`, `poupi-baby/data-core-sync.service.ts` |

## Gaps Conhecidos (não bloqueantes)

- **G-E-01**: `CryptoAnalyticsProcessor` retorna NULL — path OHLCV (TradingAnalytics) não afetado
- **G-E-02**: Real estate neighborhood analytics NULL — falta histórico suficiente
- **G-E-04**: Prometheus multi-process gap — usar `pipeline_runs` DB como fonte primária
- **G-E-05**: `LOG_JSON=true` não setado em produção — adicionar env var no Coolify
- **G-E-07**: Zero usuários reais em poupi-baby — ação de aquisição necessária

## O que está PRONTO para testes internos reais

- Coleta ecommerce de farmácias VTEX (17 produtos Pampers/fraldas)
- Pipeline raw → normalized → analytics de preço ecommerce
- Alertas de queda de preço via event-driven (email + Telegram)
- price-feed com source_url para links diretos ao produto (pós-migration 0016)
- Trading analytics: RSI, MA, ATR, ADX, signal, regime — via Binance real
- Prometheus + pipeline_runs para observabilidade operacional
