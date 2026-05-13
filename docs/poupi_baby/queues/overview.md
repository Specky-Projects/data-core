# Filas BullMQ — Overview

## Visão geral

O Poupi usa **BullMQ** (built on Redis) para processar trabalho assíncrono e pesado. Todas as filas são consumidas pelo **Worker** (processo separado da API).

---

## Filas registradas

Constantes em `systems/backend/src/shared/queues/queue.constants.ts`:

| Constante | Nome da fila | Enfileirado por | Processado por |
|---|---|---|---|
| `SCRAPER_QUEUE` | `scraper` | `ScraperQueueService` | `ScraperProcessor` |
| `DEAL_SCORE_QUEUE` | `deal-score` | `DealScoreQueueService` | `DealScoreProcessor` |
| `REVIEW_ANALYZER_QUEUE` | `review-analyzer` | `ReviewQueueService` | `ReviewAnalyzerProcessor` |
| `MARKET_PATTERNS_QUEUE` | `market-patterns` | `MarketPatternsQueueService` | `MarketPatternsProcessor` |
| `NOTIFICATION_QUEUE` | `notification` | `NotificationQueueService` | `NotificationProcessor` |
| `CLEANUP_QUEUE` | `cleanup` | `CleanupQueueService` | `CleanupProcessor` |

---

## Fila: `scraper`

**Propósito**: scraping de uma oferta em um marketplace.

**Job type**: `sync-offer`

**Job data**:
```typescript
interface ScraperJobData {
  offerId:     string;
  marketplace: string;
  reason:      'scheduled' | 'manual' | 'price_change' | 'back_in_stock';
}
```

**Configuração**:
```typescript
{
  attempts:    4,
  backoff:     { type: 'exponential', delay: 5000 },
  removeOnComplete: 100,  // mantém últimos 100 jobs completos
  removeOnFail:     200,
}
```

**Deduplicação**: `jobId = offerId` — evita múltiplos scrapes simultâneos da mesma oferta.

**Concorrência**: global 5; por marketplace limitado por semáforos internos (Amazon=1, ML=4, outros=2).

**Gatilhos**:
- `CrawlerScheduler` (cron 15min) — enfileira todas as offers ativas
- Chamada manual via `POST /crawler/sync/:offerId`
- Após `OFFER_BACK_IN_STOCK` — re-sync com prioridade alta

---

## Fila: `deal-score`

**Propósito**: calcular deal score de uma oferta após mudança de preço.

**Job type**: `calculate-deal-score`

**Job data**:
```typescript
interface DealScoreJobData {
  offerId:    string;
  productId:  string;
  reason:     'price_updated' | 'back_in_stock' | 'manual';
}
```

**Configuração**:
```typescript
{
  attempts: 3,
  backoff:  { type: 'exponential', delay: 5000 },
}
```

**Deduplicação**: `jobId = deal-score:${offerId}` — se oferta mudar de preço várias vezes em sequência, apenas o job mais recente é processado.

**Gatilhos**:
- `OfferEventsListener` ao receber `OFFER_PRICE_UPDATED`
- `OfferEventsListener` ao receber `OFFER_BACK_IN_STOCK` (prioridade 5)

**Resultado**:
- Emite `DEAL_SCORE_CALCULATED` sempre
- Emite `DEAL_SCORE_HIGH` se `score >= 75`

---

## Fila: `review-analyzer`

**Propósito**: processar dados de reviews e calcular trust score.

**Job type**: `analyze-reviews`

**Job data**:
```typescript
interface ReviewAnalyzerJobData {
  productId:   string;
  marketplace: string;
  rating:      number | null;
  reviewCount: number | null;
  texts:       string[];   // textos dos reviews
}
```

**Configuração**:
```typescript
{
  attempts: 2,
  backoff:  { type: 'fixed', delay: 10000 },
}
```

**Deduplicação**: `jobId = review:${productId}:${marketplace}`

**Gatilhos**: chamada manual via `POST /review-intelligence/process` ou futuramente pelo Review Scraper.

---

## Fila: `market-patterns`

**Propósito**: calcular padrões sazonais e tendências de preço.

**Job type**: `compute-market-patterns`

**Job data**:
```typescript
interface MarketPatternsJobData {
  productId:   string;
  marketplace: string;
  reason:      'price_updated' | 'scheduled' | 'manual';
}
```

**Configuração**:
```typescript
{
  attempts: 2,
  backoff:  { type: 'exponential', delay: 15000 },
}
```

**Deduplicação**: `jobId = mp:${productId}:${marketplace}`

**Gatilhos**:
- `OfferEventsListener` ao receber `OFFER_PRICE_UPDATED`
- `MarketIntelligenceScheduler` (cron 02:00 diário)

---

## Fila: `notification`

**Propósito**: enviar emails transacionais.

**Job type**: `send-notification`

**Job data**:
```typescript
interface NotificationJobData {
  userId:    string;
  channel:   'email';
  template:  'price_alert' | 'deal_high_score' | 'trust_low_score' | 'incident_alert';
  payload:   Record<string, unknown>;  // dados específicos do template
  priority:  'low' | 'normal' | 'high';
}
```

**Configuração**:
```typescript
{
  attempts: 3,
  backoff:  { type: 'exponential', delay: 5000 },
}
```

**Sem deduplicação** — cada notificação é única.

**Gatilhos**:
- `NotificationTriggerListener` ao receber `ALERT_TRIGGERED`
- `NotificationTriggerListener` ao receber `DEAL_SCORE_HIGH`
- `NotificationTriggerListener` ao receber `TRUST_SCORE_CHANGED` (newScore < 30)
- `NotificationTriggerListener` ao receber `INCIDENT_DETECTED` (severity high/critical)

---

## Fila: `cleanup`

**Propósito**: purge periódico de dados antigos para controle de crescimento do banco.

**Job types**:

| Job | O que faz |
|---|---|
| `cleanup-scraper-metrics` | Remove `ScraperMetric` mais antigos que `retentionDays` |
| `cleanup-user-events` | Remove `UserEvent` mais antigos que `retentionDays` (padrão 90 dias) |
| `cleanup-ai-incidents` | Remove `AiIncident` com status `resolved` ou `acknowledged` mais antigos que 30 dias |

**Configuração**:
```typescript
{
  attempts:          1,   // sem retry — cleanup pode falhar sem problema
  removeOnComplete:  true,
  removeOnFail:      true,
}
```

**Deduplicação**: `jobId = cleanup-<type>-<YYYY-MM-DD>` — garante que cada job de cleanup roda uma vez por dia.

**Gatilho**: `CleanupQueueService` (cron `0 4 * * *` — 04:00 diariamente).

---

## Padrão de implementação: QueueService

Cada fila tem um service correspondente que encapsula a lógica de enfileiramento:

```typescript
@Injectable()
export class DealScoreQueueService {
  constructor(
    @InjectQueue(DEAL_SCORE_QUEUE) private readonly queue: Queue,
  ) {}

  async enqueue(offerId: string, productId: string, reason: string, priority?: number) {
    await this.queue.add(
      CALCULATE_DEAL_SCORE_JOB,
      { offerId, productId, reason } satisfies DealScoreJobData,
      {
        jobId:    `deal-score:${offerId}`,   // deduplicação
        priority: priority ?? 0,
        ...DEAL_SCORE_JOB_DEFAULTS,
      },
    );
  }
}
```

---

## Padrão de implementação: Processor

```typescript
@Processor(DEAL_SCORE_QUEUE)
export class DealScoreProcessor extends WorkerHost {
  constructor(
    private readonly dealScoreService: DealScoreService,
    private readonly eventBus: EventBusService,
  ) { super(); }

  async process(job: Job<DealScoreJobData>): Promise<void> {
    const { offerId, productId } = job.data;

    const result = await this.dealScoreService.calculate(offerId);
    if (!result) return;   // histórico insuficiente — sem erro, sem retry

    this.eventBus.emit(DOMAIN_EVENTS.DEAL_SCORE_CALCULATED, {
      offerId, productId, score: result.score, label: result.label,
    });

    if (result.score >= 75) {
      this.eventBus.emit(DOMAIN_EVENTS.DEAL_SCORE_HIGH, { ... });
    }
  }
}
```

---

## Monitoramento

Via API admin (requer `role=admin`):

```bash
# Stats
GET /crawler/queue/stats

# Jobs falhos
GET /crawler/queue/failed

# Retry falhos
POST /crawler/queue/retry

# Pausar worker
POST /crawler/queue/pause

# Retomar worker
POST /crawler/queue/resume

# Limpar completed
DELETE /crawler/queue/completed
```

Via dashboard operacional:
```
http://localhost:3000/operacional
```
Mostra gráfico de barra com waiting/active/delayed/failed em tempo real.

---

## Considerações de escalabilidade

- **Jobs com mesmo jobId**: BullMQ descarta silenciosamente se o job ainda está pending. Se já foi processado, um novo job com mesmo ID é aceito normalmente.
- **Filas por módulo**: cada módulo registra sua própria fila com `BullModule.registerQueue()`. A conexão Redis é compartilhada via `BullModule.forRootAsync()` no `AppModule`.
- **Prioridade**: BullMQ suporta `priority` numérica — maior número = maior prioridade. `OFFER_BACK_IN_STOCK` enfileira deal-score com `priority: 5`.
- **Dead letter**: jobs que excedem `attempts` ficam em `failed`. Monitorar regularmente e fazer retry ou investigar.
