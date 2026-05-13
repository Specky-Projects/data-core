# Backend — Integrações externas

---

## Gmail (Nodemailer)

**Uso**: envio de emails transacionais (alertas de preço, deal score alto, incidentes admin).

**Configuração**:
```env
GMAIL_USER="remetente@gmail.com"
GMAIL_APP_PASSWORD="xxxx xxxx xxxx xxxx"  # senha de app, não a senha normal
```

**Como criar senha de app Gmail**:
1. Ativar autenticação em 2 fatores na conta Google
2. Acessar: conta.google.com → Segurança → Senhas de app
3. Criar nova senha para "Outro (personalizado)" → nome "Poupi"
4. Usar a senha gerada (16 caracteres sem espaços)

**Templates de email** (implementados em `NotificationsService`):
| Template | Trigger | Destinatário |
|---|---|---|
| `price_alert` | `ALERT_TRIGGERED` | Dono do alerta |
| `deal_high_score` | `DEAL_SCORE_HIGH` (score >= 75) | Usuários com alerta ativo para o produto |
| `trust_low_score` | `TRUST_SCORE_CHANGED` (newScore < 30) | Usuários monitorando o produto |
| `incident_alert` | `INCIDENT_DETECTED` (high/critical) | `ADMIN_EMAIL` |

---

## Stripe

**Uso**: pagamentos de planos premium (mercado internacional).

**Configuração**:
```env
STRIPE_SECRET_KEY="sk_live_..."       # ou sk_test_... em dev
STRIPE_WEBHOOK_SECRET="whsec_..."
STRIPE_PRICE_ID_PREMIUM="price_..."
```

**Fluxo**:
1. Frontend chama `POST /billing/checkout` com `planId`
2. Backend cria `checkout.session` via `stripe.checkout.sessions.create()`
3. Retorna `checkoutUrl` para o frontend redirecionar
4. Stripe redireciona para `FRONTEND_URL/billing?success=true` após pagamento
5. Stripe envia webhook `checkout.session.completed` para `POST /billing/webhook/stripe`
6. Backend valida assinatura com `stripe.webhooks.constructEvent(rawBody, signature, WEBHOOK_SECRET)`
7. Chama `BillingService.activatePremium(userId, plan, 'stripe', subscriptionId)`

**Webhook deve receber o body raw** (não parseado pelo Express/NestJS) — use `rawBody: true` no middleware.

---

## MercadoPago

**Uso**: pagamentos de planos premium (mercado brasileiro).

**Configuração**:
```env
MP_ACCESS_TOKEN="APP_USR-..."
MP_WEBHOOK_SECRET="..."   # opcional — para validar notificações
```

**Fluxo**:
1. Backend cria `preference` via MP SDK
2. Retorna `init_point` (URL de checkout do MP)
3. MP envia notificação IPN para `POST /billing/webhook/mercadopago`
4. Backend consulta `GET /v1/payments/{paymentId}` para confirmar status
5. Se `status === 'approved'` → `BillingService.activatePremium(...)`

---

## Sentry

**Uso**: monitoramento de erros em produção.

**Configuração**:
```env
SENTRY_DSN="https://xxx@sentry.io/xxx"
```

**Setup**: `src/instrument.ts` deve ser importado **antes** do NestJS bootstrap (já configurado em `main.ts`).

**O que é capturado**:
- Exceções não tratadas (unhandled exceptions)
- Erros HTTP 5xx automaticamente via `SentryFilter`
- Erros em processadores de fila (BullMQ)

**O que NÃO é capturado** (por design):
- Erros em `@OnEvent()` handlers — são silenciados intencionalmente
- Scrapes com falha esperada (CAPTCHA, NOT_FOUND) — são métricas normais

---

## Providers de IA (AI Ops)

Usado pelo `IncidentAnalyzer` para diagnosticar incidentes operacionais.

**Configuração**:
```env
AI_PROVIDER="mock"    # mock | claude | openai
CLAUDE_API_KEY="sk-ant-..."
OPENAI_API_KEY="sk-..."
```

**Seleção de provider** (em `AiOpsModule`):
```typescript
// Lógica da factory
if (provider === 'claude' && claude.isAvailable())  return claude;
if (provider === 'openai' && openai.isAvailable())  return openai;
return mock;  // fallback seguro
```

**MockProvider**: retorna resposta hardcoded sem custo — padrão em dev/test.

**ClaudeProvider**: usa `claude-3-haiku` por padrão (barato, rápido para análises de ops).

**OpenAIProvider**: usa `gpt-4o-mini` por padrão.

**Interface do provider** (`IAiProvider`):
```typescript
interface IAiProvider {
  analyze(prompt: string): Promise<AiAnalysisResult>;
  isAvailable(): boolean;
}
```

---

## Redis

**Uso duplo**:
1. **Cache** (via `CacheService`): TTL padrão 5min; rate limiting via sliding window counter
2. **Filas BullMQ**: persistência de jobs, retry state, delayed jobs

**Configuração**:
```env
REDIS_URL="redis://localhost:6379"
# Ou com auth:
REDIS_URL="redis://:senha@host:6379"
```

**Docker** (recomendado para dev):
```bash
docker run -d --name poupi-redis \
  -p 6379:6379 \
  redis:7-alpine \
  redis-server --maxmemory 256mb --maxmemory-policy allkeys-lru
```

**Keys usadas pelo CacheService** (prefixo `poupi:`):
```
poupi:rate:<marketplace>:<window>  → contador sliding window
poupi:scrape:<url-hash>            → cache de scrape recente
poupi:product:<id>                 → cache de produto
```

---

## PostgreSQL

**Versão**: 16

**Configuração**:
```env
DATABASE_URL="postgresql://user:password@host:5432/poupi"
```

**Docker** (dev):
```bash
docker run -d --name poupi-postgres \
  -e POSTGRES_DB=poupi \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -p 5432:5432 \
  postgres:16
```

**Extensões necessárias**: nenhuma especial (UUID gerado pelo Prisma via `uuid()` do PostgreSQL nativo).

**Backups** (produção):
- Script `infra/backups/scripts/pg-backup.sh` configurado como cron job no serviço `backup` do docker-compose
- Roda diariamente às 02:00 UTC
- Ativar com: `docker compose --profile backup up -d backup`

---

## Google OAuth (NextAuth — fluxo server-side)

O OAuth acontece no **frontend** (NextAuth), mas o backend é notificado para criar/atualizar o usuário.

**Fluxo**:
```
Usuário clica "Entrar com Google"
  ↓
NextAuth redireciona para Google OAuth
  ↓
Google retorna code para callback do NextAuth
  ↓
NextAuth callback chama POST /auth/sync no backend
  Headers: x-internal-secret: <INTERNAL_SECRET>
  Body: { email, name }
  ↓
Backend faz upsert do usuário (sem senha)
Backend retorna { accessToken: JWT }
  ↓
NextAuth armazena o JWT na sessão
```

**Configuração do frontend**:
```env
NEXTAUTH_SECRET="segredo-para-criptografar-sessao"
NEXT_PUBLIC_BACKEND_URL="http://localhost:3001"
INTERNAL_SECRET="mesmo-valor-que-no-backend"
GOOGLE_CLIENT_ID="xxx.apps.googleusercontent.com"
GOOGLE_CLIENT_SECRET="GOCSPX-..."
```
