# Backend — Constraints

Limitações técnicas, de design e operacionais que afetam decisões de implementação.

---

## Constraints de banco de dados

### PriceHistory não tem productId direto
`PriceHistory` só tem `offerId`. Para filtrar histórico por produto ou marketplace, é necessário:
1. Buscar `Offer.id` pelo `productId` + `marketplace`
2. Usar `offerId IN (offerIds)` na query de history

```typescript
// CORRETO
const offers = await prisma.offer.findMany({ where: { productId, marketplace: { name } } });
const offerIds = offers.map(o => o.id);
const history = await prisma.priceHistory.findMany({ where: { offerId: { in: offerIds } } });

// ERRADO — campo não existe
await prisma.priceHistory.findMany({ where: { productId } }); // ❌
```

### MarketPattern usa `computedAt`, não `updatedAt`
O modelo `MarketPattern` não tem campo `updatedAt` — usa `computedAt` para registrar quando foi calculado.

```typescript
// CORRETO
orderBy: { computedAt: 'desc' }

// ERRADO
orderBy: { updatedAt: 'desc' } // ❌ campo não existe
```

### Product não tem campo `name`
O campo de nome do produto é `title` (não `name`).

```typescript
// CORRETO
product.title

// ERRADO
product.name // ❌ campo não existe
```

### Soft-delete: sempre filtrar deletedAt
Queries em `User`, `Product` e `Offer` devem incluir `{ deletedAt: null }`:

```typescript
// CORRETO
prisma.product.findMany({ where: { deletedAt: null } })

// Sem o filtro retorna registros deletados também ⚠️
```

---

## Constraints de arquitetura

### Handlers @OnEvent nunca devem lançar
Qualquer exceção em um handler `@OnEvent()` é silenciada pelo EventEmitter2, o que pode mascarar erros silenciosamente. A convenção é:

```typescript
@OnEvent(DOMAIN_EVENTS.ALGO)
async handle(payload: Payload) {
  try {
    await this.service.doSomething(payload);
  } catch (err) {
    console.error('[MeuListener] falha:', err); // nunca throw
  }
}
```

### Semáforos de concorrência ficam em memória
Os semáforos do `ScraperProcessor` (Map<marketplace, slots>) são **in-process** — não compartilhados entre instâncias do worker. Em multi-instância, cada worker tem seu próprio contador. Isso é aceitável com uma instância; em escala horizontal, precisaria de Redis-based semaphore.

### JobId garante deduplicação de fila, não idempotência completa
BullMQ descarta jobs com o mesmo `jobId` se o job anterior ainda está na fila. Mas se o job já foi processado (completed/failed), um novo job com o mesmo ID **será enfileirado normalmente**. Não é um lock de execução única.

### DealScoreService retorna null com histórico insuficiente
Se uma oferta tem menos de 7 registros de `PriceHistory`, `calculate()` retorna `null`. Qualquer código que chama `calculate()` deve verificar o resultado antes de usá-lo.

---

## Constraints de scraping

### Sem headless browser
Os scrapers usam `axios` + `cheerio` (parsing de HTML estático). Páginas que dependem de JavaScript para renderizar conteúdo (SPAs com React/Vue) não são suportadas. Alternativas futuras: Puppeteer, Playwright.

### Rate limits por marketplace são conservadores
Limites atuais:
- Amazon: 1 simultâneo (muito sensível a scraping)
- ML: 4 simultâneos
- Outros: 2 simultâneos

Aumentar sem cuidado resulta em bloqueios por IP ou CAPTCHA.

### Scrapers podem retornar null se estrutura do HTML mudar
Marketplaces atualizam seus layouts frequentemente. Se o scraper não encontrar o seletor CSS esperado, pode retornar `price: null` ou lançar `PARSE_ERROR`. O `IncidentDetector` detecta padrões de `PARSE_ERROR` contínuos.

---

## Constraints de notificação

### Gmail tem limite de envio
Gmail SMTP via senha de app tem limite de ~500 emails/dia. Para volume maior, migrar para SendGrid, AWS SES ou similar.

### ADMIN_EMAIL é opcional
Se `ADMIN_EMAIL` não estiver configurado, emails de incidente são silenciosamente ignorados (sem log de aviso). Verificar configuração em produção.

---

## Constraints de IA (AI Ops)

### MockProvider em desenvolvimento
O padrão é `AI_PROVIDER=mock`, que retorna análises hardcoded. Em produção, configurar `claude` ou `openai` e fornecer a API key correspondente.

### Custo de tokens em incidentes frequentes
Cada incidente detectado faz uma chamada de IA. Em marketplaces com muita instabilidade, isso pode gerar custo significativo com Claude/OpenAI. Usar `MockProvider` para ambientes de staging.

### IncidentDetector não cria duplicados
Se já existe um incidente `open` para o marketplace, não cria um novo. Isso evita spam, mas significa que um incidente mal fechado pode suprimir novos alertas.

---

## Constraints de analytics

### getTopProducts parseia JSON em memória
`AnalyticsService.getTopProducts()` carrega todos os `UserEvent` do tipo `product_view` e parseia o campo `payload` (JSON string) em memória. Com volume alto, essa query pode ser lenta. Considerar campo `productId` separado ou índice GIN no futuro.

### UserEvent.userId é nullable
Eventos anônimos (sem login) têm `userId = null`. Queries de `getActiveUsers()` usam `COUNT(DISTINCT userId)` — eventos anônimos não são contados.

---

## Constraints do worker

### Estado em memória não persiste entre restarts
Semáforos, contadores e qualquer estado do `ScraperProcessor` são perdidos no restart. Jobs que estavam `active` no BullMQ são retomados automaticamente no próximo restart (BullMQ recupera estado do Redis).

### Worker sem HTTP server
O worker não tem porta exposta — não é possível fazer health checks HTTP diretos. Monitorar via:
- Logs do processo
- Estado das filas (via API `/crawler/queue/stats`)
- Métricas de scraping no dashboard

---

## Constraints de segurança

### JWT não é revogável
Tokens JWT são stateless — não é possível invalidar individualmente sem manter uma blocklist. Se um admin tiver o role rebaixado, o token antigo ainda funciona até expirar (7 dias por padrão). Para revogar imediatamente, mudar o `JWT_SECRET` invalida **todos** os tokens.

### INTERNAL_SECRET protege apenas /auth/sync
O endpoint `POST /auth/sync` valida o header `x-internal-secret`. Se o segredo vazar, qualquer parte pode criar/atualizar usuários. Manter `INTERNAL_SECRET` diferente do `JWT_SECRET`.
