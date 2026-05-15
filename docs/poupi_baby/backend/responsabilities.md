# Backend — Responsabilidades por módulo

Mapa de qual módulo é responsável por cada domínio funcional.

---

## Autenticação e identidade

**Módulo**: `AuthModule`

- Signup com email/senha
- Login com email/senha
- Sync de usuário OAuth (Google via NextAuth)
- Emissão de JWT com `{ sub, email, role }`
- Validação de token via `JwtStrategy`
- **NÃO responsável por**: autorização granular por recurso (feita nos services), OAuth UI (feito no frontend)

---

## Catálogo de produtos

**Módulo**: `ProductsModule`

- CRUD de produtos
- Detecção de produto por URL (via `ScraperDispatcher`)
- Watchlist por usuário (associação produto → usuário)
- Verificação de cota (limite de produtos por plano)
- Normalização de título para busca (`normalizedTitle`)
- **NÃO responsável por**: preços (domain de Offer), histórico (PriceHistoryModule), reviews (ReviewIntelligenceModule)

---

## Preços e ofertas

**Módulos**: `OffersModule`, `PriceHistoryModule`

- `OffersModule`: CRUD de ofertas; emission de eventos ao receber price updates
- `PriceHistoryModule`: append-only de capturas de preço; queries de histórico e resumos estatísticos
- **NÃO responsável por**: captura dos preços (CrawlerModule), detecção de deals (DealScoreModule)

---

## Scraping e coleta de dados

**Módulo**: `CrawlerModule`

- Agendamento de syncs (cron a cada 15min via `CrawlerScheduler`)
- Dispatch de scrapers por marketplace (`ScraperDispatcher`)
- Scrapers individuais: Amazon, Mercado Livre, Magalu, KaBuM!, Drogasil
- Gravação de `PriceHistory` e atualização de `Offer`
- Emissão de eventos de domínio após cada sync (`OFFER_PRICE_UPDATED`, etc.)
- Monitoramento de saúde por marketplace (`ScraperHealthService`)
- Fila de scraping (`SCRAPER_QUEUE`) e cleanup (`CLEANUP_QUEUE`)
- Controle de concorrência por marketplace (semáforos)
- Rate limiting via `CacheService`
- **NÃO responsável por**: verificação de alertas (AlertsModule), deal score (DealScoreModule)

---

## Alertas de preço

**Módulo**: `AlertsModule`

- CRUD de alertas de preço por usuário
- Verificação reativa via `AlertEventsListener` (escuta `OFFER_PRICE_UPDATED`)
- Verificação periódica via `CheckAlertsService` (cron a cada 6h — safety net)
- Emissão de `ALERT_TRIGGERED` quando meta atingida
- Desativação automática de alertas disparados (`active = false`)
- **NÃO responsável por**: envio de emails (NotificationsModule)

---

## Notificações

**Módulo**: `NotificationsModule`

- Envio de emails transacionais via Gmail SMTP
- Fila de notificações (`NOTIFICATION_QUEUE`) com retry
- `NotificationTriggerListener` escuta eventos de domínio e enfileira os emails corretos
- Templates: alerta de preço, deal alto, baixa confiança, incidente admin
- **NÃO responsável por**: push notifications, Telegram (futuro), SMS

---

## Monetização

**Módulos**: `BillingModule`, `PlansModule`, `AffiliateModule`, `PromotionsModule`

- `BillingModule`: checkout via Stripe/MercadoPago, webhooks, ativação/cancelamento de assinaturas, eventos de billing
- `PlansModule`: config estática dos planos (limites, features), verificação de acesso a features por plano
- `AffiliateModule`: geração de links de afiliado por marketplace
- `PromotionsModule`: tracking de promoções detectadas pelo scraper
- **NÃO responsável por**: provisionamento de recursos por plano (futuro — via `BillingEventsListener`)

---

## Deal Intelligence

**Módulo**: `DealScoreModule`

- Cálculo de score 0–100 por oferta
- Componentes: desconto histórico, proximidade do mínimo, estabilidade, tendência, raridade
- Processamento assíncrono via `DealScoreProcessor` (fila `DEAL_SCORE_QUEUE`)
- Emissão de `DEAL_SCORE_CALCULATED` e `DEAL_SCORE_HIGH` (score >= 75)
- **NÃO responsável por**: notificação de deals (NotificationsModule), histórico de preços (PriceHistoryModule)

---

## Review Intelligence

**Módulo**: `ReviewIntelligenceModule`

- Processamento de dados de reviews (rating, reviewCount, textos)
- Extração de keywords positivas e negativas (via config `review-keywords.ts`)
- Cálculo de Trust Score (0–100) via `TrustScoreCalculator`
- Persistência em `ReviewSummary` (upsert por productId + marketplace)
- Processamento assíncrono via `ReviewAnalyzerProcessor`
- Emissão de `TRUST_SCORE_CHANGED` quando variação >= 5pts
- **NÃO responsável por**: coleta de reviews das páginas (futuro — Review Scraper), análise por IA (fase 3)

---

## Market Intelligence

**Módulo**: `MarketIntelligenceModule`

- Análise de tendência de preço (regressão linear)
- Cálculo de volatilidade (coeficiente de variação 30d e 90d)
- Detecção de ciclos promocionais (drops > 15% como promo)
- Estimativa de próxima promoção (`nextPromoEst`)
- Análise de sazonalidade (médias por mês)
- Agendamento diário via `MarketIntelligenceScheduler` (cron 02:00)
- Processamento assíncrono via `MarketPatternsProcessor`
- **NÃO responsável por**: coleta de dados (CrawlerModule), exibição (MarketIntelligenceController)

---

## AI Ops

**Módulo**: `AiOpsModule`

- Detecção de incidentes operacionais via `IncidentDetector`
- Análise de root cause via IA (`IncidentAnalyzer` → Claude/OpenAI/Mock)
- Persistência de incidentes em `AiIncident`
- CRUD de incidentes (acknowledge, resolve)
- Emissão de `INCIDENT_DETECTED` e `INCIDENT_RESOLVED`
- **NÃO responsável por**: ação corretiva automática (futuro), alertas para usuários finais (apenas admin)

---

## Analytics

**Módulo**: `AnalyticsModule`

- Persistência de eventos de usuário (`UserEvent`) — append-only
- Queries analíticas: contagem, usuários ativos, top produtos, funil, série temporal
- `AnalyticsEventsListener` escuta eventos de domínio e registra métricas automaticamente
- **NÃO responsável por**: Google Analytics, Mixpanel (externos, gerenciados pelo frontend)

---

## Admin Dashboard

**Módulo**: `AdminModule`

- Agrega dados de múltiplos módulos para o dashboard admin
- Expõe endpoints `/admin/*` protegidos por `AdminGuard`
- Gerenciamento de usuários (listagem, promoção de role)
- **NÃO tem service próprio** — usa `PrismaService`, `ScraperHealthService`, `AnalyticsService`, `IncidentService` diretamente no controller

---

## Infraestrutura compartilhada

| Módulo | Responsabilidade |
|---|---|
| `AppConfigModule` | Validação de todas as envs no bootstrap via Zod. Falha rápido se config inválida. |
| `EventsModule` | Barramento de eventos interno. Módulo global. |
| `PrismaModule` | Cliente do banco. Módulo global. |
| `RedisCacheModule` | Cache key/value e rate limiting. |
| `shared/queues/queue.constants.ts` | Nomes de filas e tipos de job — fonte de verdade para todos os módulos. |
| `common/admin.guard.ts` | Guard de autorização admin. Usado em `AdminModule` e `AiOpsModule`. |
| `common/sentry.filter.ts` | Captura erros HTTP para o Sentry. |
