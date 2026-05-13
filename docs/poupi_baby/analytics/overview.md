# Analytics — Overview

## O que é

O módulo de analytics do Poupi rastreia eventos de comportamento de usuários para alimentar o dashboard admin, métricas de produto e funil de conversão.

É **completamente interno** — não usa Google Analytics nem Mixpanel na implementação atual. Todos os dados ficam no PostgreSQL (tabela `user_events`).

---

## Arquitetura

```
Frontend (Next.js)
  │
  POST /analytics/track { eventType, payload, sessionId }
  │
  AnalyticsController
  │
  emit ANALYTICS.USER_EVENT
  │
  AnalyticsEventsListener
  │
  analytics.trackAsync()  ← fire-and-forget
  │
  prisma.userEvent.create()
  ─────────────────────────
  Tabela: user_events
```

Além dos eventos do frontend, outros módulos emitem eventos que o `AnalyticsEventsListener` também captura:

| Evento de domínio | Registrado como |
|---|---|
| `ALERT_TRIGGERED` | `alert.triggered` no stream |
| `ALERT_CREATED` | `alert.created` no stream |
| `DEAL_SCORE_HIGH` | log de debug (sem userId disponível) |
| `BILLING_SUBSCRIPTION_ACTIVATED` | log / placeholder |

---

## Modelo de dados

**Tabela**: `user_events`

```
UserEvent {
  id:        UUID
  userId:    UUID?       -- null para eventos anônimos
  sessionId: string?     -- para tracking de sessão pré-login
  eventType: string      -- ex: "product_view"
  payload:   JSON string -- dados específicos do evento
  occurredAt: DateTime
}
```

**Retenção**: 90 dias por padrão. O `CleanupProcessor` (cron 04:00) remove eventos mais antigos.

---

## Eventos rastreados

### Eventos do frontend (via POST /analytics/track)

| eventType | Quando | Payload sugerido |
|---|---|---|
| `product_view` | Usuário abre página de produto | `{ productId, source }` |
| `price_history_view` | Usuário vê gráfico de histórico | `{ productId, marketplace }` |
| `alert_created` | Usuário cria alerta | `{ productId, targetPrice }` |
| `deal_clicked` | Usuário clica em "Ver oferta" | `{ offerId, productId, score }` |
| `upgrade_viewed` | Usuário vê tela de upgrade | `{ fromPlan, toPlan }` |
| `search_performed` | Usuário busca produto | `{ query, resultCount }` |

### Eventos automáticos (via listeners internos)

| eventType | Origem |
|---|---|
| `alert.triggered` | `AlertEventsListener` → `AnalyticsEventsListener` |
| `alert.created` | `AlertsController` → `AnalyticsEventsListener` |

---

## Queries disponíveis (AnalyticsService)

### getEventCounts(days)
Retorna contagem de eventos por tipo nos últimos N dias.
```json
{ "product_view": 1203, "alert_created": 45, "deal_clicked": 89 }
```

### getActiveUsers(days)
Número de `userId` únicos que geraram ao menos um evento.
- Eventos anônimos (`userId = null`) não são contados.

### getTopProducts(days, limit)
Produtos mais vistos. Parseia `payload` JSON dos eventos `product_view` em memória para extrair `productId`.

### getConversionFunnel(days)
Métricas do funil de conversão:
```json
{
  "productViewed":      1203,
  "priceHistoryViewed": 489,
  "alertCreated":       134,
  "dealClicked":        67
}
```

### getTimeSeries(eventType, days)
Contagem de um tipo de evento por dia:
```json
[
  { "date": "2026-05-01", "count": 45 },
  { "date": "2026-05-02", "count": 62 }
]
```

---

## Acesso via API

Todos os endpoints de leitura são protegidos por `AdminGuard`:

```
POST /analytics/track              🔒 (todos os usuários)
GET  /analytics/event-counts?days= 🔒👑
GET  /analytics/active-users?days= 🔒👑
GET  /analytics/top-products       🔒👑
GET  /analytics/funnel?days=       🔒👑
GET  /analytics/time-series        🔒👑
```

O dashboard admin (`/admin/analytics`) agrega essas queries em uma única chamada.

---

## Futuro

- **Google Analytics 4**: para analytics de produto público (heatmaps, sessões, demographic)
- **Mixpanel / PostHog**: para análise de funil avançada e cohorts
- **TimescaleDB**: migrar `user_events` para hypertable para suportar volume alto eficientemente
- **Real-time**: WebSockets ou SSE para dashboard de analytics ao vivo
