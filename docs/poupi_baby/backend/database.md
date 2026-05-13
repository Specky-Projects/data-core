# Backend — Database

Banco: **PostgreSQL 16**. ORM: **Prisma 6**.
Schema canônico: `systems/backend/prisma/schema.prisma`.

## Enums

```prisma
enum UserRole          { free  premium  admin }
enum SubscriptionPlan  { free  premium  pro  enterprise }
enum SubscriptionStatus { active  canceled  expired }
```

## Modelos

### User
Tabela: `users`

| Campo | Tipo | Observações |
|---|---|---|
| `id` | UUID PK | `@default(uuid())` |
| `name` | varchar(150) | |
| `email` | varchar(255) UNIQUE | índice `idx_users_email` |
| `passwordHash` | varchar(255) | bcrypt cost 12; usuários OAuth têm hash aleatório |
| `role` | UserRole | default `free`; `admin` libera endpoints `/admin/*` |
| `createdAt` | DateTime | |
| `deletedAt` | DateTime? | soft-delete; queries filtram `{ deletedAt: null }` |

Relações: `alerts[]`, `subscriptions[]`

---

### Marketplace
Tabela: `marketplaces`

| Campo | Tipo | Observações |
|---|---|---|
| `id` | UUID PK | |
| `name` | varchar(150) | ex: "Amazon", "Mercado Livre" |
| `baseUrl` | varchar(255) | usado pelo dispatcher para detectar scraper |
| `logoUrl` | varchar? | URL da logo |
| `active` | Boolean | default true; falso = ignorado no sync |

Relações: `offers[]`

Registros padrão criados pelo seed:
- Amazon, Mercado Livre, KaBuM!, Magazine Luiza, Americanas, Drogasil

---

### Product
Tabela: `products`

| Campo | Tipo | Observações |
|---|---|---|
| `id` | UUID PK | |
| `title` | varchar(500) | título original do produto |
| `normalizedTitle` | varchar(500) | lowercase, sem acentos — para busca fuzzy |
| `slug` | varchar(500) UNIQUE | URL-friendly identifier |
| `brand` | varchar(150)? | |
| `category` | varchar(150)? | |
| `imageUrl` | varchar? | |
| `createdAt` | DateTime | |
| `deletedAt` | DateTime? | soft-delete |

Índices:
- `idx_products_normalized_title` — busca por texto
- `idx_products_brand_category` — filtro por marca/categoria

Relações: `offers[]`, `alerts[]`, `reviewSummaries[]`, `marketPatterns[]`

---

### Offer
Tabela: `offers`

Uma oferta = um produto em um marketplace específico.

| Campo | Tipo | Observações |
|---|---|---|
| `id` | UUID PK | |
| `productId` | UUID FK → Product | cascade delete |
| `marketplaceId` | UUID FK → Marketplace | cascade delete |
| `externalId` | varchar(255) | ID do produto no marketplace (ASIN, MLB ID etc.) |
| `price` | Decimal(10,2) | preço atual sem frete |
| `freightPrice` | Decimal(10,2) | default 0 |
| `productUrl` | text | URL direta da oferta |
| `availability` | Boolean | default true |
| `updatedAt` | DateTime | auto-updated pelo Prisma |
| `lastCheckedAt` | DateTime | timestamp do último scrape |
| `deletedAt` | DateTime? | soft-delete |

Constraint UNIQUE: `(marketplaceId, externalId)` — uma oferta por produto por marketplace.

Índices: `productId`, `marketplaceId`, `price`, `availability`, `lastCheckedAt`

Relações: `product`, `marketplace`, `priceHistory[]`

---

### PriceHistory
Tabela: `price_history`

Append-only: cada scrape bem-sucedido cria uma nova linha.

| Campo | Tipo | Observações |
|---|---|---|
| `id` | UUID PK | |
| `offerId` | UUID FK → Offer | cascade delete |
| `price` | Decimal(10,2) | preço naquele momento |
| `capturedAt` | DateTime | default now() |

Índice: `(offerId, capturedAt DESC)` — otimizado para queries de histórico recente por oferta.

**Nota**: não tem `productId` nem `marketplace` direto — para filtrar por produto/marketplace, primeiro busca os `Offer.id` e depois filtra `PriceHistory.offerId IN (offerIds)`.

---

### Alert
Tabela: `alerts`

| Campo | Tipo | Observações |
|---|---|---|
| `id` | UUID PK | |
| `userId` | UUID FK → User | cascade delete |
| `productId` | UUID FK → Product | cascade delete |
| `targetPrice` | Decimal(10,2) | preço alvo desejado |
| `active` | Boolean | false = já disparou ou foi cancelado |
| `createdAt` | DateTime | |

Índices:
- `idx_alerts_user_id` — listagem por usuário
- `idx_alerts_product_active` — busca de alertas ativos por produto (usado no AlertEventsListener)

---

### ScraperHealth
Tabela: `scraper_health`

Um registro por marketplace — atualizado a cada scrape via upsert.

| Campo | Tipo | Observações |
|---|---|---|
| `id` | UUID PK | |
| `marketplace` | varchar(100) UNIQUE | chave de negócio |
| `successCount` | Int | acumulado |
| `failureCount` | Int | acumulado |
| `successRate` | Float | `successCount / total * 100` |
| `avgLatencyMs` | Float? | média móvel simples |
| `lastLatencyMs` | Int? | latência da última request |
| `errorBreakdown` | Text (JSON) | `{ "TIMEOUT": 5, "CAPTCHA": 2, ... }` |
| `lastSuccessAt` | DateTime? | |
| `lastFailureAt` | DateTime? | |
| `lastError` | varchar(500)? | mensagem do último erro |
| `lastErrorType` | varchar(50)? | tipo: TIMEOUT, CAPTCHA, NOT_FOUND etc. |
| `disabled` | Boolean | true = scraper pausado automaticamente |
| `updatedAt` | DateTime | auto-updated |

---

### ScraperMetric
Tabela: `scraper_metrics`

Append-only: uma linha por tentativa de scrape. Usada para timeline/histórico.

| Campo | Tipo | Observações |
|---|---|---|
| `id` | UUID PK | |
| `marketplace` | varchar(100) | |
| `capturedAt` | DateTime | |
| `latencyMs` | Int | |
| `success` | Boolean | |
| `errorType` | varchar(50)? | |

Índice: `(marketplace, capturedAt DESC)` — timeline por marketplace.

Purge: `CleanupProcessor` remove registros antigos (configurable via `retentionDays`).

---

### AiIncident
Tabela: `ai_incidents`

| Campo | Tipo | Observações |
|---|---|---|
| `id` | UUID PK | |
| `marketplace` | varchar(100)? | null = incidente global |
| `incidentType` | varchar(100) | ex: "high_failure_rate", "latency_spike" |
| `severity` | varchar(20) | `low \| medium \| high \| critical` |
| `inputData` | Text (JSON) | dados de saúde enviados à IA |
| `rootCause` | Text? | análise da IA |
| `suggestions` | Text (JSON array) | `["reiniciar scraper", "verificar CAPTCHA"]` |
| `confidence` | Float? | confiança da IA (0-1) |
| `aiProvider` | varchar(50)? | `claude \| openai \| mock` |
| `aiModel` | varchar(100)? | modelo específico usado |
| `aiTokensUsed` | Int? | consumo de tokens |
| `status` | varchar(30) | `open \| acknowledged \| resolved \| dismissed` |
| `resolvedAt` | DateTime? | |
| `resolutionNote` | Text? | nota ao resolver |
| `detectedAt` | DateTime | |
| `createdAt` | DateTime | |

Índices:
- `(marketplace, status)` — listagem por marketplace
- `(status, detectedAt DESC)` — listagem de abertos mais recentes

---

### ReviewSummary
Tabela: `review_summaries`

Um registro por (productId, marketplace) — upsert a cada análise.

| Campo | Tipo | Observações |
|---|---|---|
| `id` | UUID PK | |
| `productId` | UUID FK → Product | |
| `marketplace` | varchar(100) | |
| `rating` | Float? | média geral (ex: 4.3) |
| `reviewCount` | Int? | total de reviews |
| `stars1..5` | Int? | distribuição por estrela |
| `positiveKeywords` | Text (JSON) | `[{ keyword, count, category, sentiment }]` |
| `negativeKeywords` | Text (JSON) | idem |
| `aiSummary` | Text? | resumo gerado por IA (fase 3) |
| `aiPros` | Text (JSON) | `["entrega rápida", ...]` |
| `aiCons` | Text (JSON) | `["embalagem frágil", ...]` |
| `aiVerdict` | varchar(255)? | veredito curto da IA |
| `trustScore` | Int? | 0–100, calculado pelo TrustScoreCalculator |
| `trustFactors` | Text (JSON) | `{ reviewVolume, ratingConsistency, ... }` |
| `scrapedAt` | DateTime | último scrape |
| `aiAnalyzedAt` | DateTime? | última análise por IA |

Constraint UNIQUE: `(productId, marketplace)`

---

### MarketPattern
Tabela: `market_patterns`

Um registro por (productId, marketplace, patternType) — upsert a cada análise.

| Campo | Tipo | Observações |
|---|---|---|
| `id` | UUID PK | |
| `productId` | UUID FK → Product | |
| `marketplace` | varchar(100)? | null = consolidado multi-marketplace |
| `patternType` | varchar(50) | `seasonal \| promo_cycle \| volatility` |
| `monthlyAvgPrices` | Text (JSON) | `{ "01": 999.00, "11": 799.00 }` |
| `monthlyPromoRates` | Text (JSON) | taxa promocional por mês (0–1) |
| `avgDaysBetweenPromos` | Int? | ciclo médio de promoções |
| `lastPromoAt` | DateTime? | data da última promoção detectada |
| `nextPromoEst` | DateTime? | estimativa da próxima promoção |
| `priceVolatility30d` | Float? | coeficiente de variação 30 dias |
| `priceVolatility90d` | Float? | coeficiente de variação 90 dias |
| `trendDirection` | varchar(20)? | `up \| down \| stable` |
| `trendStrength` | Float? | 0–1, força da tendência |
| `computedAt` | DateTime | |

Constraint UNIQUE: `(productId, marketplace, patternType)`

---

### UserEvent
Tabela: `user_events`

Append-only analytics stream. Nunca atualizado — apenas inserido e (periodicamente) purgado.

| Campo | Tipo | Observações |
|---|---|---|
| `id` | UUID PK | |
| `userId` | UUID? | null = evento anônimo |
| `sessionId` | varchar(100)? | |
| `eventType` | varchar(100) | ex: `product_view`, `alert_created`, `deal_clicked` |
| `payload` | Text (JSON) | dados específicos do evento |
| `occurredAt` | DateTime | |

Índices:
- `(userId, occurredAt DESC)` — histórico por usuário
- `(eventType, occurredAt DESC)` — analytics por tipo de evento

Retenção: `CleanupProcessor` purga eventos mais antigos que `retentionDays` (padrão: 90 dias).

---

### Subscription
Tabela: `subscriptions`

| Campo | Tipo | Observações |
|---|---|---|
| `id` | UUID PK | |
| `userId` | UUID FK → User | |
| `plan` | SubscriptionPlan | `free \| premium \| pro \| enterprise` |
| `status` | SubscriptionStatus | `active \| canceled \| expired` |
| `provider` | varchar(50)? | `stripe \| mercadopago \| mock` |
| `providerSubscriptionId` | varchar(255)? | ID externo no gateway |
| `expiresAt` | DateTime? | null = vitalício ou free |
| `createdAt` | DateTime | |

Índices: `userId`, `status`, `(provider, providerSubscriptionId)`

---

## Relacionamentos visuais

```
User ──────────────► Alert ◄── Product ──► Offer ──► PriceHistory
  │                              │            │
  └──► Subscription              └──► ReviewSummary
                                 └──► MarketPattern

Marketplace ──────────────────────────────► Offer

ScraperHealth (1 por marketplace, sem FK)
ScraperMetric (append-only, sem FK)
AiIncident    (sem FK — marketplace é string)
UserEvent     (sem FK — userId é nullable)
```

## Convenções de nomenclatura no banco

| Camada | Convenção |
|---|---|
| Tabelas | `snake_case` (`user_events`, `price_history`) |
| Colunas | `snake_case` (`created_at`, `product_id`) |
| Índices | `idx_<tabela>_<campos>` |
| Constraints | `uq_<tabela>_<campos>` |
| Enums | `snake_case` (`user_role`, `subscription_plan`) |
| Modelos Prisma | `PascalCase` (`User`, `PriceHistory`) |
| Campos Prisma | `camelCase` (`createdAt`, `productId`) |
