# SCRAPING MATRIX — data-core platform

> Generated: 2026-05-16 | Phase D Global Scraping Audit
>
> Inventário completo de todos os collectors, scrapers, jobs agendados e workers
> da plataforma Poupi / data-core. Classifica cada unidade por status operacional,
> tecnologia, frequência e rastreabilidade.

---

## Legenda de Status

| Status | Significado |
|---|---|
| `ACTIVE_REAL_DATA` | Em produção, coletando dados reais de fonte externa |
| `ACTIVE_PLAYWRIGHT` | Em produção, usando Playwright/browser automation com fonte real |
| `MOCK_ONLY` | Collector registrado apenas para documentação/testes; dado hardcoded; NÃO agendado |
| `DISABLED` | Desativado intencionalmente; job comentado; fonte não configurada |
| `STUB` | Processador/worker declarado mas sem implementação real |

---

## 1. Collectors Registry (`collectors/`)

Collectors registrados em `CollectorRegistry` e processados pelo loop do scheduler.
O scheduler verifica `metadata.schedulable` antes de criar o job automático.

| Collector Name | Classe | Domínio | Source | Status | schedulable | Intervalo | Schema | Notas |
|---|---|---|---|---|---|---|---|---|
| `crypto.crypto_coin_ohlcv` | `CryptoCoinOHLCVCollector` | crypto | crypto_coin_exchange | `ACTIVE_REAL_DATA` | `True` | 15 min | `marketCandle v1.0.0` | Binance/CCXT; suporta multi-symbol, multi-timeframe via env SYMBOLS/TIMEFRAMES |
| `crypto.generic_price` | `GenericCryptoPriceCollector` | crypto | generic_exchange | `MOCK_ONLY` | `False` | — | `cryptoPriceSnapshot v1.0.0` | Retorna BTC-BRL hardcoded; NÃO agendado |
| `ecommerce.generic_product` | `GenericProductCollector` | ecommerce | generic_marketplace | `MOCK_ONLY` | `False` | — | `genericProduct v1.0.0` | Retorna produto demo hardcoded; NÃO agendado |
| `real_estate.generic_listing` | `GenericRealEstateCollector` | real_estate | generic_real_estate | `MOCK_ONLY` | `False` | — | `realEstateListing v1.0.0` | Retorna listing Sao Paulo demo; NÃO agendado |
| `sports_betting.generic_odds` | `GenericSportsOddsCollector` | sports_betting | generic_bookmaker | `MOCK_ONLY` | `False` | — | `genericOddsSnapshot v1.0.0` | Retorna odd demo football 1x2; NÃO agendado |

**Nota:** `ecommerce.url_scraper` (EcommerceURLScraper) NÃO está no registry — é
chamado diretamente por `run_ecommerce_url_targets_job` via CollectionTarget (target-based).

---

## 2. Domain Scrapers (`app/modules/`)

Scrapers especializados por domínio, chamados pelos domain jobs do scheduler.

### 2a. E-commerce — VTEX URL Scraper

| Collector | Classe | Tecnologia | Status | Targets ativos | Intervalo | Source(s) |
|---|---|---|---|---|---|---|
| `ecommerce.url_scraper` | `EcommerceURLScraper` | httpx + BeautifulSoup | `ACTIVE_REAL_DATA` | 17 | 2h | drogasil, drogaraia, paguemenos |

**Estratégias de extração (em ordem):**
1. VTEX Catalog API (`/api/catalog_system/pub/products/search/`) — quando product ID extraível da URL
2. JSON-LD structured data — fallback universal para qualquer loja VTEX

**Targets ativos por source:**

| Source | Targets | Produtos |
|---|---|---|
| drogasil.com.br | 6 | Pampers Confort Sec XXXG/44, XG/92 (×2), SuperSec G/26, SuperSec G/26 Kit2, Premium Care Pants XG/26 |
| drogaraia.com.br | 6 | Pampers Confort Sec XXXG/44, Premium Care G/30, SuperSec G/26, SuperSec G/26 Kit2, Premium Care Pants XG/26, Confort Sec XG/92 |
| paguemenos.com.br | 5 | Pampers Confort Sec XXXG/44, Premium Care Pants M/78, Confort Sec P/72, SuperSec P/34, Premium Care P/40 |

### 2b. Real Estate — Playwright Scraper

| Collector | Classe | Tecnologia | Status | Intervalo | Cidade | Source |
|---|---|---|---|---|---|---|
| `real_estate:daily` | `ApolarCollector` | Playwright (headless) | `ACTIVE_PLAYWRIGHT` | Diário (03:30) | Curitiba, PR | apolar.com.br |

**Parâmetros:** max_pages=2, max_listing_urls=25, páginas: /comprar, /alugar

### 2c. Crypto — OHLCV via CCXT

| Collector | Classe | Tecnologia | Status | Intervalo | Exchange | Symbols/Timeframes |
|---|---|---|---|---|---|---|
| `crypto.crypto_coin_ohlcv` | `CryptoCoinOHLCVCollector` | CCXT (async) | `ACTIVE_REAL_DATA` | 15 min | Binance (padrão) | BTC/USDT, ETH/USDT, SOL/USDT, BNB/USDT, ADA/USDT × 15m, 1h |

### 2d. Sports Odds

| Collector | Classe | Tecnologia | Status | Motivo |
|---|---|---|---|---|
| `sports_odds:recurring` | `NbaOddsCollector` (legacy) / nenhum | — | `DISABLED` | Única fonte configurada usava `https://example.com`; job comentado até fonte real ser integrada |

---

## 3. Scheduler Jobs (`scheduler/service.py` + `scheduler/jobs.py`)

| Job ID | Função | Trigger | Frequência | Status | Domínio |
|---|---|---|---|---|---|
| `collector:<name>` (×1) | `collect_raw_job` | interval | 15 min | `ACTIVE_REAL_DATA` | crypto (`crypto.crypto_coin_ohlcv`) |
| `maintenance:cleanup_stale_runs` | `cleanup_stale_runs_job` | interval | 15 min | ATIVO | infra |
| `maintenance:alert_webhook` | `alert_webhook_job` | interval | 1h | ATIVO | infra |
| `maintenance:data_retention` | `data_retention_job` | cron | dom 02:00 | ATIVO | infra |
| `pipeline:normalize` | `normalize_job` | interval | 15 min | ATIVO (se `scheduler_pipeline_enabled=True`) | pipeline |
| `pipeline:analytics` | `analytics_job` | interval | 60 min | ATIVO (se `scheduler_pipeline_enabled=True`) | pipeline |
| `ecommerce:url_scraper_targets` | `run_ecommerce_url_targets_job` | interval | 2h | `ACTIVE_REAL_DATA` | ecommerce |
| `real_estate:daily` | `run_real_estate_daily_collection` | cron | 03:30 | `ACTIVE_PLAYWRIGHT` | real_estate |
| `sports_odds:recurring` | (desativado) | — | — | `DISABLED` | sports_betting |

**Jobs agendados automaticamente pelo registry loop (apenas `schedulable=True`):**
- `collector:crypto.crypto_coin_ohlcv` — 15 min

**Skipped pelo registry loop (`schedulable=False`):**
- `collector:crypto.generic_price`
- `collector:ecommerce.generic_product`
- `collector:real_estate.generic_listing`
- `collector:sports_betting.generic_odds`

---

## 4. Workers Externos

### 4a. poupi-baby Worker (NestJS / BullMQ)

| Queue | Processor | Status | Triggers | Retry |
|---|---|---|---|---|
| `notification` | `NotificationProcessor` | ATIVO | `IncidentDetectedEvent`, manual | 3× backoff exponencial |
| `notification` (email) | `NotificationsService.sendSmartAlert()` | ATIVO | AlertTriggered (via queue) | Herda retry da queue |
| `notification` (telegram) | `TelegramService.send()` | ATIVO | AlertTriggered + IncidentDetected | Exceção propaga para BullMQ retry |

**Métricas expostas:** `/metrics` na porta 3002 (Prometheus); `/healthz` health check.

### 4b. poupi-crypto (Python APScheduler)

| Job | Trigger | Status | Notas |
|---|---|---|---|
| OHLCV push to data-core | interval (15 min) | Verificar | `push_ohlcv_batch` → data-core `/api/v1/raw` |
| Signal pull from data-core | interval | Verificar | Pull de sinais da API `candles-feed` |

---

## 5. Integrações de Saída (Downstream)

| Consumidor | Endpoint data-core | Frequência | Status |
|---|---|---|---|
| poupi-baby DataCoreSyncService | `GET /api/v1/poupi-baby/price-feed` | 2h | ATIVO |
| poupi-crypto | `POST /api/v1/crypto/push_ohlcv_batch` (push) | 15 min | Verificar |
| poupi-crypto | `GET /api/v1/crypto/candles-feed` (pull) | interval | Verificar |

---

## 6. Observabilidade

| Componente | Prometheus | Grafana | Log Fields Padrão | Health Check |
|---|---|---|---|---|
| data-core API | ✅ `:8000/metrics` | ✅ dashboard | parcial | `/health` |
| poupi-baby backend | ✅ `:3001/metrics` | ✅ poupi-baby-obs-v1 | parcial | `/healthz` |
| poupi-baby worker | ✅ `:3002/metrics` | ✅ poupi-baby-obs-v1 (row 2) | ✅ Phase C Fase 5 | `/healthz` |
| poupi-crypto API | ✅ `:8002/metrics` | pendente | pendente | pendente |
| scheduler jobs | N/A | N/A | ✅ Phase D Fase 5 | N/A |

**Campos de log padrão (Phase D Fase 5):**
`run_id`, `job`, `domain`, `source`, `status`, `duration_ms`, `collected_count`,
`persisted_count`, `normalized_count`, `failed_count`, `retry_count`,
`last_success_at` / `last_failure_at`

---

## 7. Gaps Conhecidos

| # | Gap | Impacto | Prioridade |
|---|---|---|---|
| G-01 | Sports odds sem fonte real — job desativado | Sem dados de odds | Baixa (aguarda integração) |
| G-02 | `poupi_legacy_raw_collector` ainda referenciado em `run_collection_target_by_id` | Dead code; pode gerar erro se chamado | Média |
| G-03 | `productUrl` em Offers do price-feed = base URL (sem slug) | Links de produto quebrados no app | Média |
| G-04 | `imageUrl` ausente em Offers criadas via sync | Imagens faltando no app | Baixa |
| G-05 | Push notifications não implementadas (`channel: 'push'` → dead-letter) | Canal ausente | Baixa |
| G-06 | Grafana dashboards não auto-provisionados | Setup manual necessário | Baixa |
| G-07 | poupi-crypto ↔ data-core integração não validada end-to-end | OHLCV pode não estar chegando | Alta |

---

*Atualizado em Phase D Fase 7 — Global Scraping Audit*
