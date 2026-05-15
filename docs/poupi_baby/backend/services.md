# Backend — Services

Referência de todos os services do backend com métodos públicos, dependências e comportamentos importantes.

---

## AuthService
**Módulo**: `AuthModule`
**Injeta**: `PrismaService`, `JwtService`

| Método | Assinatura | Retorno | Notas |
|---|---|---|---|
| `signup` | `(dto: SignupDto)` | `Promise<{ accessToken }>` | Hasha senha com bcrypt cost 12; lança se email já existe |
| `login` | `(dto: LoginDto)` | `Promise<{ accessToken }>` | Compara bcrypt; lança `UnauthorizedException` se inválido |
| `syncOAuthUser` | `(email: string, name: string)` | `Promise<{ accessToken }>` | Upsert user sem senha (OAuth); chamado pelo frontend via header `x-internal-secret` |
| `me` | `(userId: string)` | `Promise<User>` | Retorna dados do usuário autenticado |

**JWT payload**: `{ sub: userId, email, role }` — `role` é lido do banco no login e embutido no token.

---

## ProductsService
**Módulo**: `ProductsModule`
**Injeta**: `PrismaService`

| Método | Assinatura | Retorno | Notas |
|---|---|---|---|
| `addByUrl` | `(url: string, userId: string)` | `Promise<Product>` | Usa `ScraperDispatcher` para detectar marketplace; cria Product + Offer; dispara sync |
| `findAllByUser` | `(userId: string)` | `Promise<Product[]>` | Inclui offers com preço atual |
| `findOne` | `(id: string)` | `Promise<Product>` | Inclui offers + price history resumido |
| `update` | `(id: string, dto: UpdateProductDto)` | `Promise<Product>` | |
| `removeFromUser` | `(id: string, userId: string)` | `Promise<void>` | Soft-delete (`deletedAt = now()`) |
| `getQuotaSummary` | `(userId: string)` | `Promise<QuotaSummary>` | Verifica limite de produtos do plano atual |
| `create` | `(dto: CreateProductDto)` | `Promise<Product>` | Admin only — cria produto sem scraping |

---

## OffersService
**Módulo**: `OffersModule`
**Injeta**: `PrismaService`

| Método | Assinatura | Retorno | Notas |
|---|---|---|---|
| `findAll` | `(filters?)` | `Promise<Offer[]>` | Paginado; filtra por productId ou marketplace |
| `findOne` | `(id: string)` | `Promise<Offer>` | |
| `create` | `(dto: CreateOfferDto)` | `Promise<Offer>` | |
| `update` | `(id: string, dto: UpdateOfferDto)` | `Promise<Offer>` | |
| `remove` | `(id: string)` | `Promise<void>` | Soft-delete |

---

## AlertsService
**Módulo**: `AlertsModule`
**Injeta**: `PrismaService`

| Método | Assinatura | Retorno | Notas |
|---|---|---|---|
| `create` | `(dto: CreateAlertDto, userId: string)` | `Promise<Alert>` | Um alerta por (userId, productId) por vez |
| `myAlerts` | `(userId: string)` | `Promise<Alert[]>` | Inclui dados do produto |
| `cancel` | `(alertId: string, userId: string)` | `Promise<void>` | Verifica que o alerta pertence ao usuário; `active = false` |

**CheckAlertsService** (cron de segurança — a cada 6h):
- Varre todos os alertas ativos
- Para cada alerta, verifica se alguma oferta atual tem `price <= targetPrice`
- Se sim, emite `ALERT_TRIGGERED`
- Safety net para eventos perdidos durante downtime

---

## CrawlerService
**Módulo**: `CrawlerModule`
**Injeta**: `PrismaService`, `CacheService`, `EventBusService`, `ScraperDispatcher`

| Método | Assinatura | Retorno | Notas |
|---|---|---|---|
| `crawlUrl` | `(url: string)` | `Promise<ScrapedData>` | Scrape sem persistência — retorna dados brutos |
| `syncOffer` | `(offerId: string)` | `Promise<void>` | Ciclo completo: scrape → salva PriceHistory → atualiza Offer → emite eventos |
| `getOfferForQueue` | `(offerId: string)` | `Promise<Offer>` | Usado pelo ScraperProcessor antes do scrape |

**Comportamento do `syncOffer`**:
1. Busca Offer com produto + marketplace
2. Scrape via `ScraperDispatcher.scrape(url)`
3. Salva `PriceHistory` se preço captado
4. Atualiza `Offer.price`, `availability`, `lastCheckedAt`
5. `ScraperHealthService.record(marketplace, success, latencyMs, error)`
6. Se preço mudou → `emit(OFFER_PRICE_UPDATED)`
7. Se availability mudou → `emit(OFFER_BACK_IN_STOCK)` ou `emit(OFFER_OUT_OF_STOCK)`
8. Se falhou → `emit(OFFER_SCRAPE_FAILED)`

---

## ScraperHealthService
**Módulo**: `CrawlerModule`
**Injeta**: `PrismaService`, `IncidentDetector` (optional)
**Exportado por**: `CrawlerModule`

| Método | Assinatura | Retorno | Notas |
|---|---|---|---|
| `record` | `(marketplace, success, latencyMs, error?)` | `Promise<void>` | Upsert no `ScraperHealth`; insere `ScraperMetric`; chama `IncidentDetector.evaluate()` |
| `getAll` | `()` | `Promise<ScraperHealth[]>` | Ordena por successRate DESC |
| `getRanking` | `()` | `Promise<RankingEntry[]>` | Versão compacta para o dashboard |
| `getOne` | `(marketplace: string)` | `Promise<ScraperHealth>` | |
| `getTimeline` | `(marketplace, days)` | `Promise<TimelinePoint[]>` | Agrupa ScraperMetric por hora |
| `getFailureReasons` | `(marketplace, days)` | `Promise<FailureReason[]>` | Breakdown de errorType |
| `isDisabled` | `(marketplace: string)` | `Promise<boolean>` | |
| `pruneOldMetrics` | `(retentionDays: number)` | `Promise<void>` | Chamado pelo CleanupProcessor |

---

## DealScoreService
**Módulo**: `DealScoreModule`
**Injeta**: `PrismaService`

| Método | Assinatura | Retorno | Notas |
|---|---|---|---|
| `calculate` | `(offerId: string)` | `Promise<DealScoreResult \| null>` | Retorna null se histórico insuficiente (< 7 pontos) |
| `calculateForProduct` | `(productId: string)` | `Promise<DealScoreResult \| null>` | Melhor score entre todas as offers do produto |

**DealScoreResult**:
```typescript
{
  score: number,          // 0–100
  label: string,          // "Oferta excelente" | "Boa oferta" | "Preço comum" | "Cuidado"
  emoji: string,          // 🔥 | ✅ | ℹ️ | ⚠️
  labelColor: string,     // hex color
  components: {
    historicalDiscount: number,    // peso 40% — desconto vs média histórica
    allTimeLowProximity: number,   // peso 25% — proximidade do mínimo histórico
    priceStability: number,        // peso 15% — estabilidade do preço
    trend: number,                 // peso 12% — tendência de queda
    promoRarity: number,           // peso 8% — raridade do desconto atual
  },
  context: {
    allTimeLow: number,
    avgPrice90d: number,
    currentPrice: number,
  }
}
```

---

## NotificationsService
**Módulo**: `NotificationsModule`
**Injeta**: `PrismaService`, Nodemailer (transporter)

| Método | Assinatura | Retorno | Notas |
|---|---|---|---|
| `sendPriceAlert` | `(payload: AlertEmailPayload)` | `Promise<void>` | Email "seu alerta foi ativado" |
| `sendDealHighScore` | `(payload: DealEmailPayload)` | `Promise<void>` | Email "oferta imperdível" (score >= 75) |
| `sendTrustLowScore` | `(payload: TrustEmailPayload)` | `Promise<void>` | Email "produto com reviews preocupantes" |
| `sendIncidentAlert` | `(payload: IncidentEmailPayload)` | `Promise<void>` | Email para admin; skip se `ADMIN_EMAIL` não configurado |

Todos usam Gmail SMTP via `GMAIL_USER` + `GMAIL_APP_PASSWORD`.

---

## ReviewIntelligenceService
**Módulo**: `ReviewIntelligenceModule`
**Injeta**: `PrismaService`

| Método | Assinatura | Retorno | Notas |
|---|---|---|---|
| `getByProduct` | `(productId: string)` | `Promise<ReviewSummary[]>` | Uma por marketplace |
| `processReviews` | `(data: ReviewData)` | `Promise<ReviewSummary>` | Extrai keywords, calcula trust score, upsert no banco |

**TrustScoreCalculator** (calculado dentro de processReviews):
- Fatores: `reviewVolume`, `ratingConsistency`, `positiveSentimentRatio`, `verifiedPurchaseRate`, `recency`
- Score 0–100; >= 70 = Confiável (verde), >= 40 = Moderado (amarelo), < 40 = Baixa confiança (vermelho)

---

## MarketIntelligenceService
**Módulo**: `MarketIntelligenceModule`
**Injeta**: `PrismaService`

| Método | Assinatura | Retorno | Notas |
|---|---|---|---|
| `getPattern` | `(productId, marketplace)` | `Promise<MarketPattern \| null>` | |
| `getAllPatterns` | `(productId)` | `Promise<MarketPattern[]>` | |
| `getDownwardTrends` | `(minStrength?, limit?)` | `Promise<Product[]>` | Produtos com `trendDirection = 'down'` e força >= threshold |
| `getUpcomingPromos` | `(withinHours?, limit?)` | `Promise<MarketPattern[]>` | Padrões com `nextPromoEst` dentro do janela |
| `analyzeProduct` | `(productId, marketplace)` | `Promise<MarketPattern>` | Carrega histórico, calcula padrões, persiste |
| `analyzeRecent` | `(hoursBack)` | `Promise<void>` | Batch — analisa todos os produtos com atividade recente |

**Cálculos em `analyzeProduct`**:
- **Tendência de preço**: regressão linear simples sobre histórico
- **Volatilidade**: coeficiente de variação (CV%) nos últimos 30 e 90 dias
- **Médias mensais**: agrupa PriceHistory por mês, calcula média
- **Ciclo promocional**: detecta drops > 15% como promoção; calcula intervalo médio entre promos
- **Estimativa da próxima promo**: `lastPromoAt + avgDaysBetweenPromos`

---

## AnalyticsService
**Módulo**: `AnalyticsModule`
**Injeta**: `PrismaService`
**Exportado por**: `AnalyticsModule`

| Método | Assinatura | Retorno | Notas |
|---|---|---|---|
| `track` | `(input: TrackEventInput)` | `Promise<void>` | Persiste UserEvent; nunca lança |
| `trackAsync` | `(input: TrackEventInput)` | `void` | Fire-and-forget (não await) |
| `getEventCounts` | `(days: number)` | `Promise<Record<string, number>>` | groupBy eventType nos últimos N dias |
| `getActiveUsers` | `(days: number)` | `Promise<number>` | COUNT DISTINCT userId com evento nos últimos N dias |
| `getTopProducts` | `(days, limit)` | `Promise<TopProduct[]>` | Parseia payload JSON para contar productId em `product_view` |
| `getConversionFunnel` | `(days)` | `Promise<FunnelData>` | Conta: produto visto → histórico visto → alerta criado → deal clicado |
| `getTimeSeries` | `(eventType, days)` | `Promise<TimeSeriesPoint[]>` | Agrupa por dia (ISO slice 0-10) |

---

## BillingService
**Módulo**: `BillingModule`
**Injeta**: `PrismaService`, `PlansService`, `EventBusService`, gateway (Stripe/MP/Mock)

| Método | Assinatura | Retorno | Notas |
|---|---|---|---|
| `getStatus` | `(userId: string)` | `Promise<SubscriptionStatus>` | Busca subscription ativa mais recente |
| `createCheckout` | `(userId, planId)` | `Promise<{ checkoutUrl }>` | Delega para gateway ativo |
| `cancelSubscription` | `(userId, subscriptionId)` | `Promise<void>` | |
| `activatePremium` | `(userId, plan, provider, providerSubId)` | `Promise<void>` | Cria/atualiza Subscription; emit `SUBSCRIPTION_ACTIVATED`; se upgrade, emit `PLAN_UPGRADED` |
| `deactivatePremium` | `(userId)` | `Promise<void>` | Marca subscription como `canceled`; emit `SUBSCRIPTION_CANCELLED` |
| `handleWebhook` | `(provider, payload)` | `Promise<void>` | Roteador de webhooks — chama `activatePremium` ou `deactivatePremium` |

**Gateways disponíveis** (selecionados via env `BILLING_PROVIDER`):
- `MockGateway` — padrão de dev, sempre aprova
- `StripeGateway` — usa `STRIPE_SECRET_KEY`
- `MercadoPagoGateway` — usa `MP_ACCESS_TOKEN`

---

## IncidentService
**Módulo**: `AiOpsModule`
**Injeta**: `PrismaService`
**Exportado por**: `AiOpsModule`

| Método | Assinatura | Retorno | Notas |
|---|---|---|---|
| `getOpen` | `()` | `Promise<AiIncident[]>` | status = `open` |
| `getRecent` | `(limit: number)` | `Promise<AiIncident[]>` | Todos os status, ordem por detectedAt DESC |
| `acknowledge` | `(id: string)` | `Promise<AiIncident>` | status → `acknowledged` |
| `resolve` | `(id: string, note?: string)` | `Promise<AiIncident>` | status → `resolved`; salva `resolutionNote` e `resolvedAt`; emit `INCIDENT_RESOLVED` |

---

## IncidentDetector
**Módulo**: `AiOpsModule`
**Injeta**: `PrismaService`, `IncidentAnalyzer`, `EventBusService`
**Exportado por**: `AiOpsModule`

| Método | Assinatura | Retorno | Notas |
|---|---|---|---|
| `evaluate` | `(marketplace: string)` | `Promise<void>` | Chamado pelo ScraperHealthService após cada scrape; verifica se threshold de falhas foi atingido |

**Thresholds padrão**:
- Taxa de sucesso < 50% (últimos 20 requests) → severity `high`
- Taxa de sucesso < 25% → severity `critical`
- Se já existe incidente `open` para o marketplace, não cria duplicado

**Fluxo interno**:
1. Busca métricas recentes do marketplace
2. Calcula taxa de sucesso
3. Se abaixo do threshold: cria `AiIncident` no banco
4. Chama `IncidentAnalyzer.analyze()` — envia dados à IA (Claude/OpenAI/Mock)
5. Atualiza incidente com rootCause + suggestions da IA
6. Emite `INCIDENT_DETECTED`

---

## CacheService
**Módulo**: `RedisCacheModule`
**Injeta**: Redis client

| Método | Assinatura | Retorno | Notas |
|---|---|---|---|
| `get` | `<T>(key: string)` | `Promise<T \| null>` | |
| `set` | `(key, value, ttlSeconds?)` | `Promise<void>` | TTL padrão: 300s (5min) |
| `del` | `(key: string)` | `Promise<void>` | |
| `acquireRateLimit` | `(key, maxRequests, windowSeconds)` | `Promise<boolean>` | Sliding window counter; retorna `false` se rate limit atingido |

---

## PlansService
**Módulo**: `PlansModule`
**Injeta**: `PrismaService`

| Método | Assinatura | Retorno | Notas |
|---|---|---|---|
| `getConfig` | `(plan: SubscriptionPlan)` | `PlanConfig` | Retorna config estática do plano |
| `getUserPlan` | `(userId: string)` | `Promise<SubscriptionPlan>` | Busca subscription ativa do usuário |
| `checkFeature` | `(userId, feature)` | `Promise<boolean>` | Verifica se o plano do usuário tem acesso à feature |

**PlanConfig fields**:
- `maxProducts: number` — limite de produtos monitorados
- `syncPriority: 'low' | 'normal' | 'high'` — prioridade na fila de scraping
- `dealScore: boolean` — acesso ao deal score
- `csvExport: boolean` — exportação de dados
- `apiAccess: boolean` — acesso à API pública (futuro)
- `advancedAnalytics: boolean` — analytics avançados
