# Backend — Runbook

Guia operacional: como levantar, configurar, administrar e depurar o backend.

---

## Pré-requisitos

- Node.js >= 20
- Docker + Docker Compose
- Redis rodando em `localhost:6379`
- PostgreSQL rodando em `localhost:5432`

---

## Setup inicial

### 1. Instalar dependências
```bash
cd systems/backend
npm install
```

### 2. Configurar variáveis de ambiente
```bash
cp .env.example .env
# editar .env com os valores reais
```

Variáveis obrigatórias:
```env
DATABASE_URL="postgresql://postgres:postgres@localhost:5432/poupi"
JWT_SECRET="mude-para-segredo-forte-em-prod"
INTERNAL_SECRET="segredo-compartilhado-com-frontend"
REDIS_URL="redis://localhost:6379"
GMAIL_USER="seu-email@gmail.com"
GMAIL_APP_PASSWORD="senha-de-app-gmail"
FRONTEND_URL="http://localhost:3000"
```

### 3. Criar banco e aplicar schema
```bash
npx prisma migrate dev      # cria tabelas
```

### 4. Popular dados iniciais
```bash
npx prisma db seed          # cria admin.poupi@gmail.com + marketplaces padrão
```

### 5. Iniciar
```bash
npm run start:dev           # modo watch — API em :3001
```

Em outro terminal (worker):
```bash
cd systems/worker
npm run start:dev
```

---

## Variáveis de ambiente completas

| Variável | Obrigatória | Padrão | Descrição |
|---|---|---|---|
| `DATABASE_URL` | ✅ | — | Connection string PostgreSQL |
| `JWT_SECRET` | ✅ | — | Chave para assinar tokens JWT |
| `INTERNAL_SECRET` | ✅ | — | Segredo para comunicação frontend→backend (OAuth sync) |
| `REDIS_URL` | ✅ | `redis://localhost:6379` | URL do Redis |
| `FRONTEND_URL` | ✅ | `http://localhost:3000` | Usado em CORS e links de email |
| `GMAIL_USER` | ✅ (emails) | — | Email remetente |
| `GMAIL_APP_PASSWORD` | ✅ (emails) | — | Senha de app Gmail (não a senha normal) |
| `ADMIN_EMAIL` | ⚠️ | — | Email para receber alertas de incidente; se ausente, skip silencioso |
| `AI_PROVIDER` | ❌ | `mock` | `mock \| claude \| openai` |
| `CLAUDE_API_KEY` | ❌ | — | Obrigatório se `AI_PROVIDER=claude` |
| `OPENAI_API_KEY` | ❌ | — | Obrigatório se `AI_PROVIDER=openai` |
| `STRIPE_SECRET_KEY` | ❌ | — | Stripe |
| `STRIPE_WEBHOOK_SECRET` | ❌ | — | Verificação de webhooks Stripe |
| `STRIPE_PRICE_ID_PREMIUM` | ❌ | — | Price ID do plano premium no Stripe |
| `MP_ACCESS_TOKEN` | ❌ | — | MercadoPago |
| `MP_WEBHOOK_SECRET` | ❌ | — | Verificação de webhooks MP |
| `SENTRY_DSN` | ❌ | — | DSN do Sentry para monitoramento |

---

## Administração de usuários admin

### Listar admins
```bash
npm run seed:admin -- list
```

### Promover usuário existente a admin
```bash
npm run seed:admin -- grant usuario@email.com
```

### Revogar admin
```bash
npm run seed:admin -- revoke usuario@email.com
```

### Via API (já autenticado como admin)
```bash
curl -X PATCH http://localhost:3001/admin/users/<userId>/role \
  -H "Authorization: Bearer <JWT>" \
  -H "Content-Type: application/json" \
  -d '{"role": "admin"}'
```

---

## Comandos Prisma

```bash
# Aplicar migrações em dev (cria migration file)
npx prisma migrate dev --name <nome-da-migracao>

# Aplicar migrações em prod (sem criar arquivos)
npx prisma migrate deploy

# Inspecionar banco via GUI
npx prisma studio

# Regenerar Prisma Client após mudança de schema
npx prisma generate

# Reset completo do banco (CUIDADO — apaga tudo)
npx prisma migrate reset
```

---

## Docker Compose (produção / dev integrado)

```bash
# Subir tudo
docker compose up -d

# Apenas infra (Postgres + Redis)
docker compose up -d postgres redis

# Logs da API
docker compose logs -f api

# Logs do worker
docker compose logs -f worker

# Parar tudo
docker compose down

# Rebuild após mudança de código
docker compose build api worker && docker compose up -d api worker
```

---

## Monitorar filas BullMQ

Sem UI por padrão. Para inspecionar via API:

```bash
# Stats da fila de scraping
curl http://localhost:3001/crawler/queue/stats \
  -H "Authorization: Bearer <ADMIN_JWT>"

# Reprocessar jobs falhos
curl -X POST http://localhost:3001/crawler/queue/retry \
  -H "Authorization: Bearer <ADMIN_JWT>"

# Pausar worker
curl -X POST http://localhost:3001/crawler/queue/pause \
  -H "Authorization: Bearer <ADMIN_JWT>"
```

---

## Dashboard operacional (frontend)

Acesse `http://localhost:3000/operacional` com conta de admin.

Mostra em tempo real:
- Taxa de sucesso e latência por scraper
- Jobs na fila BullMQ (waiting, active, failed, delayed)
- Timeline de scraping (24h / 7d / 14d)
- Breakdown de tipos de falha
- Tabela health detalhada

Auto-refresh a cada 30s.

---

## Dashboard admin (endpoints)

```bash
# Overview completo da plataforma
curl http://localhost:3001/admin/overview \
  -H "Authorization: Bearer <ADMIN_JWT>"

# Incidentes abertos
curl http://localhost:3001/admin/incidents \
  -H "Authorization: Bearer <ADMIN_JWT>"

# Analytics dos últimos 7 dias
curl http://localhost:3001/admin/analytics?days=7 \
  -H "Authorization: Bearer <ADMIN_JWT>"
```

---

## Depuração comum

### JWT inválido / 401
1. Verifique se `JWT_SECRET` no backend e no frontend são iguais
2. Token expirado? Relogar — `expiresIn: '7d'` por padrão

### Admin sempre recebe 403
1. Verifique se o usuário tem `role=admin` no banco:
   ```bash
   npm run seed:admin -- list
   ```
2. Se role estiver correto mas ainda 403: o token foi emitido antes da mudança. Relogar para gerar novo token com role atualizado.

### Emails não chegam
1. Verifique `GMAIL_USER` e `GMAIL_APP_PASSWORD`
2. Senha de app Gmail: conta Google → Segurança → Senhas de app (requer 2FA ativo)
3. Teste o transporter:
   ```bash
   curl -X POST http://localhost:3001/notifications/test \
     -H "Authorization: Bearer <ADMIN_JWT>"
   ```

### Scrapers com alta taxa de falha
1. Acesse `/operacional` para ver o breakdown de erros
2. TIMEOUT: aumentar `requestTimeout` no scraper específico
3. CAPTCHA: reduzir concorrência do marketplace, rotacionar User-Agent
4. NOT_FOUND: produto removido — verificar URL da oferta

### Fila BullMQ travada
```bash
# Ver jobs falhos
curl http://localhost:3001/crawler/queue/failed \
  -H "Authorization: Bearer <ADMIN_JWT>"

# Retry
curl -X POST http://localhost:3001/crawler/queue/retry \
  -H "Authorization: Bearer <ADMIN_JWT>"

# Se Redis reiniciou e fila está inconsistente — limpar completed
curl -X DELETE http://localhost:3001/crawler/queue/completed \
  -H "Authorization: Bearer <ADMIN_JWT>"
```

---

## Logs relevantes

```
# Eventos emitidos (EventBus)
[EventBusService] Emitting offer.price_updated { offerId: ... }

# Scrape
[ScraperProcessor] Processing job sync-offer for offerId=xxx
[CrawlerService] Scrape OK amazon in 1823ms

# Deal Score
[DealScoreProcessor] Score calculado: 82 (🔥 Oferta excelente)

# Incidente
[IncidentDetector] Taxa de falha amazon: 67% — criando incidente high
[AiOpsModule] Incidente detectado: high_failure_rate (amazon)

# Notificação
[NotificationProcessor] Enviando email price_alert para user@email.com
```
