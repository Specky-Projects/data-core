# Arquitetura do Backend — Poupi

## Visão Geral

```
src/
├── auth/               # Autenticação JWT + Google OAuth
├── users/ (via prisma) # Gerenciamento de usuários
├── products/           # CRUD de produtos
├── offers/             # Ofertas por marketplace
├── price-history/      # Histórico de preços
├── alerts/             # Alertas de preço por usuário
├── notifications/      # Envio de e-mails (Nodemailer)
│
├── crawler/            # Orquestração de scraping
│   └── scrapers/       # Scrapers por marketplace
│       ├── base.scraper.ts         ← UA pool, fetch + retry, parsePrice
│       ├── amazon.scraper.ts       ← 10+ seletores CSS + fallback regex
│       ├── mercadolivre.scraper.ts ← __NEXT_DATA__ JSON + CSS fallback
│       ├── dispatcher.ts           ← Roteador por loja + scraper genérico
│       └── index.ts
│
├── cache/              # Redis: cache de preços + rate limiter + JWT blacklist
├── plans/              # Configuração e limites dos planos Free/Premium
├── affiliate/          # Geração de URLs de afiliado por marketplace
├── promotions/         # Scoring e publicação de promoções no Telegram
│
└── billing/            # Pagamentos e assinaturas
    └── gateways/
        ├── gateway.interface.ts    ← Contrato comum (SOLID)
        ├── mercadopago.gateway.ts  ← Pix, Cartão, Boleto
        ├── stripe.gateway.ts       ← Cartão, Subscription
        └── mock.gateway.ts         ← Desenvolvimento/testes
```

---

## Módulos

### `crawler/scrapers/`
Cada scraper segue o mesmo contrato: recebe uma URL e retorna `ScrapedProduct`.

| Arquivo | Responsabilidade |
|---|---|
| `base.scraper.ts` | UA rotativo, `fetchPage` com retry/backoff, `parsePrice` BR |
| `amazon.scraper.ts` | 10+ seletores CSS, fallback regex, detecção de CAPTCHA |
| `mercadolivre.scraper.ts` | Extração via JSON embutido (`__NEXT_DATA__`), fallback CSS |
| `dispatcher.ts` | Detecta loja pela URL → roteia para scraper correto |

**Para adicionar um novo marketplace:**
1. Criar `<loja>.scraper.ts` exportando `scrape<Loja>(url)`
2. Adicionar padrão em `STORES` no `dispatcher.ts`

---

### `cache/`
Redis com fallback gracioso (sem Redis → operação normal, sem cache).

| Feature | Chave Redis | TTL |
|---|---|---|
| Cache de preço | `price:v1:<md5[:16]>` | 5 min |
| Rate limit (token bucket) | `ratelimit:<domain>` | 1h |
| JWT blacklist | `jwt:blacklist:<sha256>` | TTL do token |

Rate limits por domínio (tokens/segundo):

| Domínio | tokens/s | max |
|---|---|---|
| amazon.com.br | 1 | 5 |
| mercadolivre.com.br | 2 | 10 |
| outros | 2 | 10 |

---

### `plans/`
Centraliza limites dos planos. **Nunca** use `if (plan === 'free')` espalhado — use `PlansService.getUserPlan()`.

| Feature | Free | Premium |
|---|---|---|
| Produtos monitorados | 5 | Ilimitado |
| Intervalo de verificação | 60 min | 15 min |
| Histórico de preços | 7 dias | 365 dias |
| Alertas Telegram | ✗ | ✓ |
| Canal de promoções | ✗ | ✓ |
| Preço | Grátis | R$ 19,90/mês |

---

### `billing/gateways/`
Abstração via interface `PaymentGateway`. O `BillingService` seleciona o gateway automaticamente:

```
MP_ACCESS_TOKEN     → MercadoPagoGateway
STRIPE_SECRET_KEY   → StripeGateway
(nenhum)            → MockGateway  ← apenas desenvolvimento
```

---

### `promotions/`
Score ponderado para detectar promoções reais:

| Critério | Pontos |
|---|---|
| Desconto ≥ 15% | +0.30 |
| Desconto ≥ 25% | +0.20 |
| Desconto ≥ 40% | +0.20 |
| Menor preço histórico | +0.20 |
| ≥ 10 verificações (confiável) | +0.10 |
| Publicado nas últimas 24h | −0.50 |

Publica no canal Telegram quando `score ≥ 0.5`.

---

### `affiliate/`
Gera URLs de afiliado com UTMs por loja.

| Loja | Estratégia |
|---|---|
| Amazon | `?tag=AMAZON_AFFILIATE_TAG` |
| Mercado Livre | UTM + `partner_id` |
| Outros | UTMs genéricos |

---

## Variáveis de Ambiente

```env
# Banco
DATABASE_URL=

# Auth
JWT_SECRET=

# E-mail
GMAIL_USER=
GMAIL_APP_PASSWORD=

# CORS
FRONTEND_URL=

# Redis (opcional — fallback gracioso sem Redis)
REDIS_URL=redis://localhost:6379

# Afiliados (opcional)
AMAZON_AFFILIATE_TAG=
ML_PARTNER_ID=

# Telegram (opcional)
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHANNEL_ID=

# Billing — MercadoPago (opcional)
MP_ACCESS_TOKEN=
MP_WEBHOOK_SECRET=

# Billing — Stripe (opcional)
STRIPE_SECRET_KEY=
STRIPE_WEBHOOK_SECRET=
STRIPE_PRICE_ID_PREMIUM=
```

---

## Fluxo do Crawler

```
CrawlerScheduler (cron 5min)
  └─ CrawlerService.getActiveOffers()
       └─ para cada oferta (lotes de 5, Promise.allSettled):
            1. CacheService.getCachedPrice()     → cache hit? retorna
            2. CacheService.acquireRateLimit()   → aguarda slot
            3. dispatcher.scrapeProduct()        → detecta loja → scraper
            4. prisma.offer.update()             → atualiza preço
            5. prisma.priceHistory.create()      → apenas se preço mudou
            6. CacheService.setCachedPrice()     → armazena no cache
```
