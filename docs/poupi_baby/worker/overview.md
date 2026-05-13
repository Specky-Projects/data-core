# Worker — Overview

## O que é

Processo NestJS separado que consome todas as filas BullMQ. **Não tem servidor HTTP** — é puramente um consumidor de jobs.

Roda como um serviço Docker independente (`poupi-worker`), podendo ser escalado horizontalmente sem afetar a API.

**Localização**: `systems/worker/`

---

## Por que separado da API?

| Razão | Detalhe |
|---|---|
| Isolamento de falhas | Um job de scraping travado não derruba a API |
| Escala independente | Workers podem ser adicionados sem escalar a API |
| Recursos dedicados | Scrapers são CPU/memory-intensos; isolados não afetam latência da API |
| Restart seguro | Worker pode ser reiniciado sem downtime de API |

---

## Filas consumidas

| Fila | Processor | Concorrência | O que processa |
|---|---|---|---|
| `scraper` | `ScraperProcessor` | 5 jobs simultâneos | Scrape de URL por marketplace |
| `deal-score` | `DealScoreProcessor` | default pool | Cálculo de deal score 0-100 |
| `review-analyzer` | `ReviewAnalyzerProcessor` | default pool | Análise de reviews e trust score |
| `market-patterns` | `MarketPatternsProcessor` | default pool | Padrões sazonais e tendências |
| `notification` | `NotificationProcessor` | default pool | Envio de emails via Gmail |
| `cleanup` | `CleanupProcessor` | default pool | Purge de dados antigos |

---

## Módulos importados

O `WorkerModule` importa todos os módulos que contêm processors:

```typescript
@Module({
  imports: [
    // Infraestrutura
    AppConfigModule,
    EventsModule,
    PrismaModule,
    RedisCacheModule,
    BullModule,   // root connection

    // Módulos com processors
    DealScoreModule,          // DealScoreProcessor
    ReviewIntelligenceModule, // ReviewAnalyzerProcessor
    MarketIntelligenceModule, // MarketPatternsProcessor
    NotificationsModule,      // NotificationProcessor
    AiOpsModule,              // IncidentDetector (usado pelo ScraperHealthService)
    AnalyticsModule,          // AnalyticsEventsListener
    AlertsModule,             // AlertEventsListener
    BillingModule,            // BillingEventsListener
    OffersModule,             // OfferEventsListener

    // Crawler (ScraperProcessor + CleanupProcessor)
    CrawlerModule,
  ],
})
export class WorkerModule {}
```

O worker também herda todos os `@OnEvent()` listeners dos módulos importados — ele reage a eventos de domínio da mesma forma que a API.

---

## Bootstrap

```typescript
// systems/worker/src/main.ts
async function bootstrap() {
  const app = await NestFactory.createApplicationContext(WorkerModule);
  // Sem app.listen() — sem servidor HTTP

  process.on('SIGTERM', async () => {
    await app.close(); // graceful shutdown — drena jobs em andamento
  });
}
```

---

## Variáveis de ambiente

Compartilha as mesmas envs do backend:

```env
DATABASE_URL=        # mesmo banco da API
REDIS_URL=           # mesmo Redis (filas compartilhadas)
JWT_SECRET=          # não necessário, mas herdado do .env compartilhado
GMAIL_USER=          # para NotificationProcessor
GMAIL_APP_PASSWORD=
AI_PROVIDER=         # para IncidentAnalyzer
CLAUDE_API_KEY=
OPENAI_API_KEY=
ADMIN_EMAIL=         # para emails de incidente
WORKER_CONCURRENCY=5 # concorrência do ScraperProcessor
```

---

## Docker

```yaml
# docker-compose.yml
worker:
  build:
    context: .
    dockerfile: systems/worker/Dockerfile
  container_name: poupi-worker
  environment:
    WORKER_CONCURRENCY: 5
  depends_on:
    - postgres
    - redis
  restart: unless-stopped
```

---

## Escalabilidade horizontal

Para processar mais jobs simultâneos, adicionar réplicas:

```yaml
worker:
  deploy:
    replicas: 3   # 3 workers × 5 concurrent = 15 scrapes simultâneos
```

**Cuidado**: semáforos de concorrência por marketplace são in-process. Em 3 réplicas, cada worker tem seus próprios slots — o limite por marketplace é multiplicado pelo número de réplicas. Ajuste `WORKER_CONCURRENCY` adequadamente.

---

## Monitoramento do worker

O worker não tem endpoint HTTP para health check. Opções:

1. **Estado das filas** (via API admin):
   ```
   GET /crawler/queue/stats   → jobs waiting/active/failed
   ```

2. **Métricas de scraping** (via dashboard operacional):
   ```
   http://localhost:3000/operacional
   ```

3. **Logs do container**:
   ```bash
   docker compose logs -f worker
   ```

4. **Sentry**: erros de jobs são capturados automaticamente.

---

## Graceful shutdown

Ao receber `SIGTERM` (deploy, restart), o worker:
1. Para de aceitar novos jobs
2. Aguarda jobs em andamento completarem (BullMQ drena graciosamente)
3. Fecha conexões com PostgreSQL e Redis
4. Encerra o processo

Jobs que estavam em `active` no momento do kill abrupto são retomados no próximo start (BullMQ persiste estado no Redis).
