# Backend — Domain Events

## Visão geral

O `EventBusService` (baseado em `EventEmitter2`, módulo global) é o barramento de eventos interno do Poupi. Módulos emitem eventos com `eventBus.emit()` e escutam com `@OnEvent()`.

**Regras imutáveis:**
1. Eventos são dispatch fire-and-forget — não bloqueiam o emitente
2. Handlers nunca lançam exceções — erros são `catch`ados e logados
3. Eventos são internos — nunca expostos via HTTP
4. Payloads são imutáveis após emissão
5. Cada evento tem um `traceId` UUID para correlação cross-módulo

## Envelope padrão

```typescript
interface DomainEvent<T = unknown> {
  readonly type:      DomainEventType;   // string constant ex: 'offer.price_updated'
  readonly payload:   T;                 // payload tipado por evento
  readonly timestamp: Date;              // quando foi emitido
  readonly traceId:   string;            // UUID para correlação de logs
}
```

## Catálogo completo de eventos

### `offer.price_updated`
**Emitido por**: `CrawlerService.syncOffer()` — após detectar que o preço da oferta mudou.

```typescript
interface OfferPriceUpdatedPayload {
  offerId:      string;
  productId:    string;
  marketplace:  string;  // nome do marketplace, ex: "Amazon"
  oldPrice:     number | null;
  newPrice:     number;
  availability: boolean;
}
```

**Listeners**:
| Listener | Módulo | O que faz |
|---|---|---|
| `AlertEventsListener` | `alerts` | Verifica se algum alerta ativo tem `targetPrice >= newPrice`; se sim, dispara o alerta |
| `OfferEventsListener` | `offers` | Enfileira deal-score e market-patterns para a oferta |
| `AnalyticsEventsListener` | `analytics` | Registra métrica interna (não rastreada como UserEvent) |

---

### `offer.back_in_stock`
**Emitido por**: `CrawlerService.syncOffer()` — quando `offer.availability` muda de `false` para `true`.

Payload: mesmo tipo de `OfferPriceUpdatedPayload`.

**Listeners**:
| Listener | O que faz |
|---|---|
| `OfferEventsListener` | Enfileira deal-score com prioridade 5 (alta) |

---

### `offer.out_of_stock`
**Emitido por**: `CrawlerService.syncOffer()` — quando `offer.availability` muda de `true` para `false`.

Payload: mesmo tipo de `OfferPriceUpdatedPayload`.

**Listeners**: nenhum ainda (reservado para notificações futuras).

---

### `offer.scrape_failed`
**Emitido por**: `CrawlerService.syncOffer()` — quando o scraper lança exceção.

```typescript
interface OfferScrapeFailedPayload {
  offerId:      string;
  marketplace:  string;
  errorType:    string;   // TIMEOUT | CAPTCHA | NOT_FOUND | PARSE_ERROR | UNKNOWN
  errorMsg:     string;
  attemptsMade: number;
}
```

**Listeners**:
| Listener | O que faz |
|---|---|
| `IncidentDetector` (injetado em `ScraperHealthService`) | Avalia se a taxa de falhas do marketplace atingiu threshold crítico; se sim, cria `AiIncident` |

---

### `deal.score_calculated`
**Emitido por**: `DealScoreProcessor` — após calcular o score de uma oferta.

```typescript
interface DealScoreCalculatedPayload {
  offerId:     string;
  productId:   string;
  marketplace: string;
  score:       number;   // 0–100
  label:       string;   // "Oferta excelente", "Boa oferta" etc.
}
```

**Listeners**:
| Listener | O que faz |
|---|---|
| `AnalyticsEventsListener` | Log de debug (score calculado) |

---

### `deal.score_high`
**Emitido por**: `DealScoreProcessor` — apenas quando `score >= 75`.

Payload: mesmo tipo de `DealScoreCalculatedPayload`.

**Listeners**:
| Listener | O que faz |
|---|---|
| `NotificationTriggerListener` | Busca usuários com alertas ativos para o produto; enfileira email de "oferta imperdível" |

---

### `review.scraped`
**Emitido por**: `ReviewIntelligenceService` — após processar reviews de um produto.

```typescript
interface ReviewScrapedPayload {
  productId:   string;
  marketplace: string;
  rating:      number | null;
  reviewCount: number | null;
}
```

**Listeners**: nenhum ativo (reservado).

---

### `review.trust_score_changed`
**Emitido por**: `ReviewIntelligenceService` — quando o trust score muda >= 5 pontos.

Payload: mesmo tipo de `ReviewScrapedPayload` + campos de score.

**Listeners**:
| Listener | O que faz |
|---|---|
| `NotificationTriggerListener` | Se `newScore < 30` e `newScore < oldScore`, enfileira email de aviso de baixa confiança |

---

### `alert.triggered`
**Emitido por**: `AlertEventsListener` — após desativar um alerta que teve sua meta atingida.

```typescript
interface AlertTriggeredPayload {
  alertId:      string;
  userId:       string;
  productId:    string;
  marketplace:  string;
  currentPrice: number;
  targetPrice:  number;
  dealScore?:   number;   // se disponível no momento
}
```

**Listeners**:
| Listener | O que faz |
|---|---|
| `NotificationTriggerListener` | Busca dados do usuário/produto/oferta no banco; enfileira email de alerta de preço |
| `AnalyticsEventsListener` | Registra evento `alert.triggered` no stream de analytics |

---

### `alert.created`
**Emitido por**: `AlertsController` — após criar um novo alerta.

Payload: `AlertTriggeredPayload` (campos de preço atual e target).

**Listeners**:
| Listener | O que faz |
|---|---|
| `AnalyticsEventsListener` | Registra evento `alert.created` no stream de analytics |

---

### `ai-ops.incident_detected`
**Emitido por**: `IncidentDetector.evaluate()` — após criar um `AiIncident` no banco.

```typescript
interface IncidentDetectedPayload {
  incidentId:   string;
  marketplace:  string;
  severity:     string;   // low | medium | high | critical
  incidentType: string;
}
```

**Listeners**:
| Listener | O que faz |
|---|---|
| `NotificationTriggerListener` | Apenas para `severity === 'high' \| 'critical'`; envia email para `ADMIN_EMAIL` |

---

### `ai-ops.incident_resolved`
**Emitido por**: `AiOpsController` (endpoint `PATCH /ai-ops/incidents/:id/resolve`).

Payload: `IncidentDetectedPayload`.

**Listeners**: nenhum ativo.

---

### `billing.subscription_activated`
**Emitido por**: `BillingService.activatePremium()` — após processar webhook de pagamento confirmado.

Payload: `{ userId, plan, provider }` (tipagem interna do BillingModule).

**Listeners**:
| Listener | O que faz |
|---|---|
| `BillingEventsListener` | Log + placeholder para provisionamento de recursos |
| `AnalyticsEventsListener` | Registra evento de conversão |

---

### `billing.subscription_cancelled`
**Emitido por**: `BillingService.deactivatePremium()`.

Payload: `{ userId }`.

**Listeners**:
| Listener | O que faz |
|---|---|
| `BillingEventsListener` | Log + placeholder para desprovisionamento |

---

### `billing.plan_upgraded`
**Emitido por**: `BillingService.activatePremium()` — apenas na primeira ativação (upgrade de free para pago).

Payload: `{ userId, plan }`.

**Listeners**:
| Listener | O que faz |
|---|---|
| `NotificationTriggerListener` | Reservado — email de boas-vindas premium |

---

### `analytics.user_event`
**Emitido por**: `AnalyticsController.track()` — quando o frontend chama `POST /analytics/track`.

```typescript
interface TrackEventInput {
  userId?:    string;
  sessionId?: string;
  eventType:  string;   // product_view | deal_clicked | upgrade_viewed | ...
  payload?:   Record<string, unknown>;
}
```

**Listeners**:
| Listener | O que faz |
|---|---|
| `AnalyticsEventsListener` | Chama `analytics.trackAsync(input)` — persiste no banco de forma assíncrona |

---

## Como emitir um evento (exemplo)

```typescript
import { EventBusService } from '../shared/events/event-bus.service';
import { DOMAIN_EVENTS }   from '../shared/events/domain-events';

@Injectable()
export class MyService {
  constructor(private readonly eventBus: EventBusService) {}

  async doSomething() {
    // ... lógica de negócio ...

    this.eventBus.emit(DOMAIN_EVENTS.OFFER_PRICE_UPDATED, {
      offerId:     'abc',
      productId:   'xyz',
      marketplace: 'Amazon',
      oldPrice:    199.90,
      newPrice:    149.90,
      availability: true,
    });
    // fire-and-forget: não await, não bloqueia
  }
}
```

## Como escutar um evento (exemplo)

```typescript
import { Injectable } from '@nestjs/common';
import { OnEvent }    from '@nestjs/event-emitter';
import { DOMAIN_EVENTS, OfferPriceUpdatedPayload } from '../shared/events/domain-events';

@Injectable()
export class MyEventsListener {
  @OnEvent(DOMAIN_EVENTS.OFFER_PRICE_UPDATED)
  async handlePriceUpdated(payload: OfferPriceUpdatedPayload): Promise<void> {
    try {
      // lógica reativa
    } catch (err) {
      // NUNCA propague — apenas logue
      console.error('[MyEventsListener] erro:', err);
    }
  }
}
```

## Matriz emitentes × listeners

| Evento | Emitente | Listeners |
|---|---|---|
| `offer.price_updated` | CrawlerService | AlertEventsListener, OfferEventsListener |
| `offer.back_in_stock` | CrawlerService | OfferEventsListener |
| `offer.out_of_stock` | CrawlerService | — |
| `offer.scrape_failed` | CrawlerService | IncidentDetector (via ScraperHealthService) |
| `deal.score_calculated` | DealScoreProcessor | AnalyticsEventsListener |
| `deal.score_high` | DealScoreProcessor | NotificationTriggerListener |
| `review.scraped` | ReviewIntelligenceService | — |
| `review.trust_score_changed` | ReviewIntelligenceService | NotificationTriggerListener |
| `alert.triggered` | AlertEventsListener | NotificationTriggerListener, AnalyticsEventsListener |
| `alert.created` | AlertsController | AnalyticsEventsListener |
| `ai-ops.incident_detected` | IncidentDetector | NotificationTriggerListener |
| `ai-ops.incident_resolved` | AiOpsController | — |
| `billing.subscription_activated` | BillingService | BillingEventsListener |
| `billing.subscription_cancelled` | BillingService | BillingEventsListener |
| `billing.plan_upgraded` | BillingService | NotificationTriggerListener |
| `analytics.user_event` | AnalyticsController | AnalyticsEventsListener |
