# Backend — Overview

## O que é

API REST construída com **NestJS** (Node.js + TypeScript). É o núcleo do Poupi: autentica usuários, orquestra scrapers, calcula deal scores, detecta incidentes com IA, envia notificações e expõe todos os dados ao frontend.

Roda em **duas instâncias separadas**:
- `api` — servidor HTTP na porta `3001`, atende requisições do frontend
- `worker` — processo sem HTTP, consome filas BullMQ (scrapers, deal-score, notificações etc.)

## Stack

| Camada | Tecnologia |
|---|---|
| Framework | NestJS 11 + TypeScript 5 |
| ORM | Prisma 6 + PostgreSQL 16 |
| Cache | Redis 7 (`redis` npm package) |
| Filas | BullMQ 5 + Redis |
| Autenticação | Passport + JWT (`passport-jwt`) |
| Email | Nodemailer (Gmail SMTP) |
| Monitoramento | Sentry (`@sentry/nestjs`) |
| Agendamento | `@nestjs/schedule` (cron jobs) |
| IA | Claude (Anthropic), OpenAI, ou Mock |

## Estrutura de módulos

```
src/
├── config/          Validação de envs via Zod (falha no bootstrap se inválido)
├── shared/
│   ├── events/      EventBusService — pub/sub interno (@Global)
│   └── queues/      Constantes e tipos das filas BullMQ
│
├── prisma/          PrismaService — acesso ao banco (@Global)
├── cache/           CacheService — Redis key/value + rate limiting
├── auth/            JWT strategy, signup, login, Google OAuth sync
├── common/          AdminGuard, filtro Sentry
│
├── products/        Catálogo de produtos, watchlist por usuário
├── marketplaces/    Registry de marketplaces ativos
├── offers/          Ofertas por marketplace + listener de eventos
├── price-history/   Histórico de preços capturados
├── alerts/          Alertas de preço + listener reativo
│
├── crawler/         Scrapers, scheduler, health, filas de scraping/cleanup
├── notifications/   Email via Gmail, fila, listener de disparo
├── billing/         Stripe/MercadoPago, webhooks, assinaturas
├── plans/           Config de planos (free/premium/pro/enterprise)
├── affiliate/       Links de afiliado por marketplace
├── promotions/      Tracking de promoções detectadas
│
├── deal-score/      Motor de pontuação de deals (0–100)
├── review-intelligence/  Análise de reviews + trust score (0–100)
├── market-intelligence/  Padrões sazonais, volatilidade, tendências
├── ai-ops/          Detecção de incidentes operacionais via IA
├── analytics/       Rastreamento de eventos de usuário
│
└── admin/           Dashboard operacional (requer role=admin)
```

## Padrões arquiteturais

### 1. Módulos auto-contidos
Cada domínio encapsula `controller + service + module + DTOs + listeners`. Módulos se comunicam via **EventBus** ou importando explicitamente o módulo externo e usando os services exportados.

### 2. Event-Driven (fire-and-forget)
O `EventBusService` (global, baseado em `EventEmitter2`) é a espinha dorsal da comunicação cross-módulo. Todos os handlers `@OnEvent()` nunca lançam exceções — erros são capturados e logados, o fluxo nunca é interrompido.

### 3. Filas para trabalho pesado
Scraping, cálculo de deal score, análise de reviews e notificações são processados pelo **worker** via BullMQ, com retry automático e backoff configurado por fila.

### 4. Soft-delete
`User`, `Product` e `Offer` têm campo `deletedAt`. Queries filtram `{ deletedAt: null }` por padrão — nunca fazem `DELETE` direto.

### 5. Segurança em camadas
- Toda rota autenticada: `@UseGuards(AuthGuard('jwt'))`
- Rotas admin: `@UseGuards(AuthGuard('jwt'), AdminGuard)` — verifica `req.user.role === 'admin'`
- `role` vem do banco, é incluído no payload JWT no login e relido em `JwtStrategy.validate()`

## Fluxo de dados

```
Frontend (Next.js :3000)
        │
        │ HTTP Bearer JWT
        ▼
API NestJS (:3001)
        │
   ┌────┴────────┐
   │             │
PostgreSQL     Redis
(Prisma)    (cache + filas)
                 │
            Worker NestJS
            (sem porta HTTP)
```

## Entry points

| Arquivo | Papel |
|---|---|
| `src/main.ts` | Bootstrap do servidor HTTP |
| `src/app.module.ts` | Root module — importa todos os módulos |
| `src/instrument.ts` | Inicialização do Sentry (deve ser importado ANTES do NestJS) |
| `prisma/schema.prisma` | Schema do banco — fonte de verdade dos modelos |
| `prisma/seed.ts` | Seed inicial (admin user + marketplaces padrão) |
| `prisma/seed-admin.ts` | CLI para grant/revoke/list admins |
