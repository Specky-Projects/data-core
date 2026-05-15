# Backend — Endpoints

Base URL: `http://localhost:3001` (dev) | `https://api.poupi.com.br` (prod)

Autenticação: `Authorization: Bearer <JWT>` em todas as rotas marcadas com 🔒.
Rotas marcadas com 👑 exigem adicionalmente `role=admin` no token.

---

## Auth — `/auth`

### `POST /auth/signup`
Cria conta com email/senha.

**Body:**
```json
{ "name": "João", "email": "joao@email.com", "password": "min8chars" }
```
**Response 201:**
```json
{ "accessToken": "eyJ..." }
```

---

### `POST /auth/login`
Login com email/senha.

**Body:**
```json
{ "email": "joao@email.com", "password": "min8chars" }
```
**Response 200:**
```json
{ "accessToken": "eyJ..." }
```

---

### `POST /auth/google` 🔒 (interno)
Callback do Google OAuth — chamado pelo frontend via NextAuth.

**Body:**
```json
{ "email": "joao@gmail.com", "name": "João Silva" }
```
**Headers:** `x-internal-secret: <INTERNAL_SECRET>`

**Response 200:**
```json
{ "accessToken": "eyJ..." }
```

---

### `GET /auth/me` 🔒
Retorna dados do usuário autenticado.

**Response 200:**
```json
{ "userId": "uuid", "email": "joao@email.com", "role": "free" }
```

---

## Products — `/products`

### `GET /products` 🔒
Lista produtos monitorados pelo usuário atual.

**Response 200:**
```json
[{ "id": "uuid", "title": "...", "slug": "...", "imageUrl": "...", "offers": [...] }]
```

---

### `POST /products/by-url` 🔒
Adiciona produto via URL + dispara scrape imediato.

**Body:**
```json
{ "url": "https://www.amazon.com.br/dp/B08N5KWB9H" }
```
**Response 201:** objeto Product com offers.

---

### `GET /products/quota` 🔒
Retorna cota de produtos do plano atual.

**Response 200:**
```json
{ "used": 3, "limit": 5, "plan": "free", "canAdd": true }
```

---

### `GET /products/:id` 🔒
Detalhe de um produto.

---

### `PATCH /products/:id` 🔒
Atualiza produto (admin ou dono).

---

### `DELETE /products/:id` 🔒
Remove produto da watchlist (soft-delete).

---

## Offers — `/offers`

### `GET /offers` 🔒
Lista todas as ofertas (paginado).

**Query params:** `page`, `limit`, `productId`, `marketplace`

---

### `POST /offers` 🔒
Cria oferta manualmente.

**Body:**
```json
{ "productId": "uuid", "marketplaceId": "uuid", "externalId": "ASIN", "price": 299.90, "productUrl": "https://..." }
```

---

### `GET /offers/:id` 🔒
Detalhe de uma oferta.

---

### `PATCH /offers/:id` 🔒
Atualiza oferta.

---

### `DELETE /offers/:id` 🔒
Soft-delete de oferta.

---

## Alerts — `/alerts`

### `POST /alerts` 🔒
Cria alerta de preço.

**Body:**
```json
{ "productId": "uuid", "targetPrice": 249.90 }
```
**Response 201:**
```json
{ "id": "uuid", "productId": "uuid", "targetPrice": 249.90, "active": true, "createdAt": "..." }
```

---

### `GET /alerts/my-alerts` 🔒
Lista alertas do usuário atual.

**Response 200:**
```json
[{ "id": "uuid", "productId": "uuid", "targetPrice": 249.90, "active": true, "product": { "title": "..." } }]
```

---

### `DELETE /alerts/:id` 🔒
Cancela alerta (sets `active = false`).

---

## Price History — `/price-history`

### `GET /price-history/product/:productId` 🔒
Histórico de preços de todas as ofertas de um produto.

**Query:** `days=90` (padrão)

---

### `GET /price-history/product/:productId/summary` 🔒
Resumo estatístico: min, max, média, variação.

---

### `GET /price-history/offer/:offerId` 🔒
Histórico de uma oferta específica.

---

### `GET /price-history/offer/:offerId/summary` 🔒
Resumo estatístico de uma oferta.

---

## Marketplaces — `/marketplaces`

### `GET /marketplaces` 🔒
Lista todos os marketplaces ativos.

---

### `POST /marketplaces` 🔒 👑
Cria marketplace.

**Body:**
```json
{ "name": "Shopee", "baseUrl": "https://shopee.com.br" }
```

---

### `GET /marketplaces/:id` 🔒
Detalhe de marketplace.

---

### `PATCH /marketplaces/:id` 🔒 👑
Atualiza marketplace.

---

### `DELETE /marketplaces/:id` 🔒 👑
Remove marketplace.

---

## Crawler — `/crawler`

### `GET /crawler/scrape?url=<URL>` 🔒
Scrape manual de URL (sem persistência — retorna dados brutos).

---

### `GET /crawler/sync/:offerId` 🔒
Dispara sync de uma oferta específica (enfileira no BullMQ).

---

### `POST /crawler/sync` 🔒 👑
Sync completo de todas as ofertas ativas.

---

### `GET /crawler/health` 🔒 👑
Saúde de todos os scrapers.

**Response 200:**
```json
[{
  "marketplace": "amazon",
  "successRate": 92.5,
  "avgLatencyMs": 2340,
  "failureCount": 3,
  "disabled": false,
  "lastError": null
}]
```

---

### `GET /crawler/health/ranking` 🔒 👑
Ranking compacto por taxa de sucesso.

---

### `GET /crawler/health/:marketplace` 🔒 👑
Saúde detalhada de um marketplace.

---

### `GET /crawler/metrics/:marketplace?days=7` 🔒 👑
Timeline por hora (ScraperMetric).

---

### `GET /crawler/metrics/:marketplace/failures?days=30` 🔒 👑
Breakdown de tipos de falha.

---

### `GET /crawler/queue/stats` 🔒 👑
Stats da fila BullMQ (waiting, active, completed, failed, delayed).

---

### `POST /crawler/queue/retry` 🔒 👑
Reprocessa jobs falhos.

---

### `POST /crawler/queue/pause` / `POST /crawler/queue/resume` 🔒 👑
Pausa/retoma o worker.

---

## Deal Score — `/deal-score`

### `GET /deal-score/offer/:offerId` 🔒
Calcula deal score de uma oferta.

**Response 200:**
```json
{
  "score": 82,
  "label": "Oferta excelente",
  "emoji": "🔥",
  "labelColor": "#22C55E",
  "components": {
    "historicalDiscount": 35,
    "allTimeLowProximity": 20,
    "priceStability": 15,
    "trend": 7,
    "promoRarity": 5
  },
  "context": {
    "allTimeLow": 149.90,
    "avgPrice90d": 219.90,
    "currentPrice": 159.90
  }
}
```

---

### `GET /deal-score/product/:productId` 🔒
Melhor deal score entre todas as ofertas do produto.

---

## Review Intelligence — `/review-intelligence`

### `GET /review-intelligence/product/:productId` 🔒
Resumo de reviews por marketplace para o produto.

**Response 200:**
```json
[{
  "marketplace": "amazon",
  "rating": 4.3,
  "reviewCount": 1243,
  "trustScore": 78,
  "positiveKeywords": [{ "keyword": "entrega rápida", "count": 245, "sentiment": "positive" }],
  "negativeKeywords": [{ "keyword": "embalagem", "count": 32, "sentiment": "negative" }],
  "label": "Confiável",
  "color": "#22C55E",
  "emoji": "✅"
}]
```

---

### `POST /review-intelligence/process` 🔒 👑
Processa reviews manualmente para um produto.

**Body:**
```json
{
  "productId": "uuid",
  "marketplace": "amazon",
  "rating": 4.3,
  "reviewCount": 1243,
  "texts": ["Ótimo produto...", "Chegou rápido..."]
}
```

---

## Market Intelligence — `/market-intelligence`

### `GET /market-intelligence/product/:productId/:marketplace` 🔒
Padrão de mercado para produto + marketplace.

**Response 200:**
```json
{
  "patternType": "seasonal",
  "trendDirection": "down",
  "trendStrength": 0.72,
  "priceVolatility30d": 0.08,
  "nextPromoEst": "2026-11-29T00:00:00.000Z",
  "monthlyAvgPrices": { "01": 999.00, "11": 799.00 }
}
```

---

### `GET /market-intelligence/product/:productId` 🔒
Todos os padrões do produto (todos os marketplaces).

---

### `GET /market-intelligence/trends/downward?minStrength=0.5&limit=20` 🔒
Produtos com tendência de queda de preço.

---

### `GET /market-intelligence/promos/upcoming?withinHours=168&limit=10` 🔒
Promoções estimadas nas próximas N horas.

---

### `POST /market-intelligence/analyze/:productId/:marketplace` 🔒 👑
Força reanálise de padrões.

---

### `POST /market-intelligence/analyze/recent?hoursBack=24` 🔒 👑
Reanálise em lote de todas as ofertas atualizadas nas últimas N horas.

---

## Analytics — `/analytics`

### `POST /analytics/track` 🔒
Rastreia evento de usuário.

**Body:**
```json
{
  "eventType": "product_view",
  "sessionId": "sess_abc123",
  "payload": { "productId": "uuid", "source": "search" }
}
```

---

### `GET /analytics/event-counts?days=7` 🔒 👑
Contagem de eventos por tipo nos últimos N dias.

**Response 200:**
```json
{ "product_view": 1203, "alert_created": 45, "deal_clicked": 89 }
```

---

### `GET /analytics/active-users?days=30` 🔒 👑
Número de usuários únicos ativos.

---

### `GET /analytics/top-products?days=7&limit=20` 🔒 👑
Produtos mais visualizados.

---

### `GET /analytics/funnel?days=30` 🔒 👑
Funil de conversão: produto visto → histórico visto → alerta criado → deal clicado.

---

### `GET /analytics/time-series?eventType=product_view&days=30` 🔒 👑
Série temporal de eventos por dia.

---

## AI Ops — `/ai-ops`

### `GET /ai-ops/incidents` 🔒 👑
Incidentes abertos.

**Response 200:**
```json
[{
  "id": "uuid",
  "marketplace": "amazon",
  "incidentType": "high_failure_rate",
  "severity": "high",
  "rootCause": "Rate limiting detectado — taxa de CAPTCHA subiu para 45%",
  "suggestions": ["Reduzir concorrência", "Rotacionar User-Agent"],
  "status": "open",
  "detectedAt": "2026-05-11T10:00:00.000Z"
}]
```

---

### `GET /ai-ops/incidents/history?limit=50` 🔒 👑
Histórico de incidentes (todos os status).

---

### `PATCH /ai-ops/incidents/:id/acknowledge` 🔒 👑
Marca incidente como reconhecido.

---

### `PATCH /ai-ops/incidents/:id/resolve` 🔒 👑
Marca incidente como resolvido.

**Body (opcional):**
```json
{ "note": "Rotação de User-Agent resolveu o problema" }
```

---

## Billing — `/billing`

### `GET /billing/status` 🔒
Status da assinatura atual.

**Response 200:**
```json
{
  "plan": "premium",
  "status": "active",
  "expiresAt": "2026-06-11T00:00:00.000Z",
  "provider": "stripe"
}
```

---

### `POST /billing/checkout` 🔒
Cria sessão de checkout (Stripe ou MercadoPago).

**Body:**
```json
{ "planId": "premium" }
```
**Response 200:**
```json
{ "checkoutUrl": "https://checkout.stripe.com/..." }
```

---

### `POST /billing/cancel` 🔒
Cancela assinatura.

---

### `POST /billing/webhook/stripe`
Webhook do Stripe (sem autenticação JWT — usa `stripe-signature` header).

---

### `POST /billing/webhook/mercadopago`
Webhook do MercadoPago.

---

## Admin — `/admin` 👑

Todos os endpoints exigem `AuthGuard('jwt') + AdminGuard`.

### `GET /admin/me`
Valida acesso admin e retorna dados do token.

**Response 200:**
```json
{ "userId": "uuid", "email": "admin@poupi.com", "role": "admin" }
```

---

### `GET /admin/overview`
Dashboard geral da plataforma.

**Response 200:**
```json
{
  "users": { "total": 1842, "admins": 2, "premium": 347 },
  "catalog": { "products": 5621, "offers": 18430 },
  "alerts": { "total": 9812, "active": 2341 },
  "ops": { "openIncidents": 1, "activeUsers7d": 423 },
  "generatedAt": "2026-05-11T14:30:00.000Z"
}
```

---

### `GET /admin/scraper-health`
Ranking de scrapers.

---

### `GET /admin/scraper-health/timeline/:marketplace?days=7`
Timeline de scraping de um marketplace.

---

### `GET /admin/analytics?days=7`
Overview de analytics: eventCounts, activeUsers, topProducts, funnel.

---

### `GET /admin/analytics/time-series?eventType=product_view&days=30`
Série temporal de um tipo de evento.

---

### `GET /admin/incidents`
Incidentes AI Ops abertos.

---

### `GET /admin/incidents/history?limit=50`
Histórico de incidentes.

---

### `GET /admin/users?page=1&limit=50&role=premium`
Lista paginada de usuários com plano ativo.

**Response 200:**
```json
{
  "users": [{
    "id": "uuid",
    "name": "João",
    "email": "joao@email.com",
    "role": "free",
    "activePlan": "free",
    "expiresAt": null,
    "createdAt": "2026-01-01T00:00:00.000Z"
  }],
  "pagination": { "total": 1842, "page": 1, "limit": 50, "pages": 37 }
}
```

---

### `PATCH /admin/users/:id/role`
Promove ou rebaixa role de usuário.

**Body:**
```json
{ "role": "premium" }
```
Valores permitidos: `free | premium | admin`

**Response 200:**
```json
{ "updated": true, "user": { "id": "uuid", "email": "...", "role": "premium" } }
```

---

## Padrões de resposta de erro

```json
// 400 Bad Request
{ "statusCode": 400, "message": "Validation failed", "errors": [...] }

// 401 Unauthorized
{ "statusCode": 401, "message": "Unauthorized" }

// 403 Forbidden (AdminGuard)
{ "statusCode": 403, "message": "Acesso restrito a administradores." }

// 404 Not Found
{ "statusCode": 404, "message": "Resource not found" }

// 500 Internal Server Error
{ "statusCode": 500, "message": "Internal server error" }
```
