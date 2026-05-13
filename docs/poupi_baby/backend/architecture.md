# Backend — Arquitetura

## Grafo de dependências de módulos

```
AppModule
├── AppConfigModule          ← Zod env validation, deve ser o primeiro
├── EventsModule (@Global)   ← EventBusService disponível em qualquer módulo
├── PrismaModule (@Global)   ← PrismaService disponível em qualquer módulo
├── RedisCacheModule         ← CacheService (key/value, rate limiting)
├── ScheduleModule           ← habilita @Cron()
├── BullModule (root)        ← conexão Redis compartilhada para todas as filas
│
├── AuthModule → PrismaModule
│
├── ProductsModule → PrismaModule
├── MarketplacesModule → PrismaModule
├── OffersModule → PrismaModule, DealScoreModule, MarketIntelligenceModule
├── PriceHistoryModule → PrismaModule
├── AlertsModule → PrismaModule, NotificationsModule
├── NotificationsModule → PrismaModule, [NOTIFICATION_QUEUE]
├── CrawlerModule → PrismaModule, AiOpsModule, [SCRAPER_QUEUE, CLEANUP_QUEUE]
│
├── PlansModule → PrismaModule
├── AffiliateModule → PrismaModule
├── PromotionsModule → PrismaModule
├── BillingModule → PrismaModule, PlansModule
│
├── DealScoreModule → PrismaModule, [DEAL_SCORE_QUEUE]
├── ReviewIntelligenceModule → PrismaModule, [REVIEW_ANALYZER_QUEUE]
├── MarketIntelligenceModule → PrismaModule, [MARKET_PATTERNS_QUEUE]
├── AiOpsModule → PrismaModule
├── AnalyticsModule → PrismaModule
│
└── AdminModule → PrismaModule, CrawlerModule, AnalyticsModule, AiOpsModule
```

## Fluxo principal: scraping → alerta → email

```
CrawlerScheduler (cron a cada 15 min)
  └─► ScraperQueueService.enqueue(offerId)
            ▼
      [BullMQ: scraper]
            ▼
      ScraperProcessor.process(job)
        ├── crawl URL
        ├── salva PriceHistory
        ├── atualiza Offer.price
        │
        ├── preço mudou?
        │   └─► emit OFFER_PRICE_UPDATED { offerId, oldPrice, newPrice, marketplace }
        │           ├─► AlertEventsListener
        │           │     ├── busca alerts { productId, active, targetPrice >= newPrice }
        │           │     ├── deactivate alert
        │           │     ├── emit ALERT_TRIGGERED { alertId, userId, productId, currentPrice }
        │           │     │       └─► NotificationTriggerListener
        │           │     │             └─► NotificationQueueService.sendPriceAlert()
        │           │     │                       ▼
        │           │     │               [BullMQ: notification]
        │           │     │                       ▼
        │           │     │               NotificationProcessor
        │           │     │                       ▼
        │           │     │               Gmail SMTP ──► user@email
        │           │     └── enqueue NotificationQueueService diretamente (caminho rápido)
        │           │
        │           ├─► OfferEventsListener
        │           │     ├── DealScoreQueueService.enqueue(offerId)
        │           │     │         ▼
        │           │     │   [BullMQ: deal-score]
        │           │     │         ▼
        │           │     │   DealScoreProcessor
        │           │     │     ├── DealScoreService.calculate(offerId) → score 0-100
        │           │     │     ├── emit DEAL_SCORE_CALCULATED
        │           │     │     └── score >= 75? emit DEAL_SCORE_HIGH
        │           │     │               └─► NotificationTriggerListener
        │           │     │                     └─► email usuários com alerta ativo
        │           │     │
        │           │     └── MarketPatternsQueueService.enqueue(offerId)
        │           │               ▼
        │           │         [BullMQ: market-patterns]
        │           │               ▼
        │           │         MarketPatternsProcessor
        │           │         └── MarketIntelligenceService.analyzeProduct(...)
        │           │               → persiste MarketPattern
        │           │
        │           └─► AnalyticsEventsListener (registra métricas internas)
        │
        ├── availability mudou?
        │   ├── voltou → emit OFFER_BACK_IN_STOCK
        │   └── saiu   → emit OFFER_OUT_OF_STOCK
        │
        └── falhou? (exception no scraper)
              ├── ScraperHealthService.record(marketplace, false, ...)
              └── IncidentDetector.evaluate(marketplace)
                    └── taxa de falha > threshold?
                          ├── cria AiIncident no banco
                          ├── IA analisa root cause (Claude/OpenAI/Mock)
                          └── emit INCIDENT_DETECTED
                                └─► NotificationTriggerListener
                                      └── severity high/critical?
                                            └─► email para ADMIN_EMAIL
```

## Módulos globais

Declarados com `@Global()` — injetáveis em qualquer módulo sem declarar `imports`:

| Módulo | Token injetável | O que provê |
|---|---|---|
| `PrismaModule` | `PrismaService` | Cliente do Prisma (acesso ao banco) |
| `EventsModule` | `EventBusService` | emit() e on() de eventos de domínio |

## Guards e decoradores de segurança

```typescript
// Rota autenticada (qualquer usuário logado)
@UseGuards(AuthGuard('jwt'))

// Rota exclusiva para admin
@UseGuards(AuthGuard('jwt'), AdminGuard)
// AdminGuard: lança ForbiddenException se req.user.role !== 'admin'
```

`JwtStrategy.validate(payload)` retorna `{ userId, email, role }` — o `role` vem do banco e é embutido no token no login.

## Padrão de módulo (template)

```typescript
@Module({
  imports: [
    PrismaModule,                                      // se usa o banco diretamente
    BullModule.registerQueue({ name: MY_QUEUE }),      // se tem processador de fila
    OtherModule,                                       // se precisa injetar service externo
  ],
  controllers: [MyController],
  providers: [
    MyService,
    MyQueueService,    // @Injectable() que injeta @InjectQueue(MY_QUEUE)
    MyProcessor,       // @Processor(MY_QUEUE) extends WorkerHost
    MyEventsListener,  // @Injectable() com @OnEvent(DOMAIN_EVENTS.XXX)
  ],
  exports: [MyService],  // só o que outros módulos precisam injetar
})
export class MyModule {}
```

## Estratégia de retry nas filas BullMQ

| Fila | Tentativas | Backoff | Notas |
|---|---|---|---|
| `scraper` | 4 | exponencial, 5s base | jobs deduplicados por offerId |
| `deal-score` | 3 | exponencial, 5s base | jobId = `deal-score:${offerId}` |
| `review-analyzer` | 2 | fixo, 10s | jobId = `review:${productId}:${marketplace}` |
| `market-patterns` | 2 | exponencial, 15s base | jobId = `mp:${productId}:${marketplace}` |
| `notification` | 3 | exponencial, 5s base | sem deduplicação (cada alerta é único) |
| `cleanup` | 1 | sem retry | jobs diários por data |

## Semáforos de concorrência no scraping

`ScraperProcessor` usa semáforos em memória (Map<string, number>):

| Marketplace | Slots simultâneos |
|---|---|
| Amazon | 1 |
| Mercado Livre | 4 |
| Magalu, KaBuM!, Drogasil | 2 |
| Outros (fallback) | 2 |

Spin-wait com poll de 200ms, timeout de 30s por slot. Garante que não sobrecarga o marketplace com requests paralelos.

## Cron jobs ativos

| Job | Schedule | Serviço | O que faz |
|---|---|---|---|
| Sync de ofertas | `*/15 * * * *` | `CrawlerScheduler` | Enfileira sync de todas as offers ativas |
| Check de alertas | `0 */6 * * *` | `CheckAlertsService` | Safety net — verifica alertas que o listener pode ter perdido |
| Análise de padrões | `0 2 * * *` | `MarketIntelligenceScheduler` | Recalcula padrões de mercado para produtos ativos |
| Cleanup diário | `0 4 * * *` | `CleanupQueueService` | Enfileira purge de métricas antigas, eventos e incidentes |

## Comunicação servidor-a-servidor (OAuth)

O frontend (NextAuth) chama `POST /auth/sync` para criar/atualizar o usuário após OAuth Google:

```
Frontend (NextAuth callback)
  │
  POST /auth/sync
  Headers: { x-internal-secret: INTERNAL_SECRET }
  Body: { email, name }
  │
  AuthService.syncOAuthUser(email, name)
  │
  upsert User no banco
  │
  retorna { accessToken: JWT }
```

O `INTERNAL_SECRET` é uma env var compartilhada entre frontend e backend — impede chamadas externas.
