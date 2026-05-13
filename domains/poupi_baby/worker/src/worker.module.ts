/**
 * worker.module.ts
 *
 * Processa todas as filas BullMQ do Poupi:
 *   - scraper          → ScraperProcessor (scraping de ofertas)
 *   - deal-score       → DealScoreProcessor (via DealScoreModule)
 *   - review-analyzer  → ReviewAnalyzerProcessor (via ReviewIntelligenceModule)
 *   - market-patterns  → MarketPatternsProcessor (via MarketIntelligenceModule)
 *   - notification     → NotificationProcessor (via NotificationsModule)
 *   - cleanup          → CleanupProcessor (via CrawlerModule)
 *
 * Também processa eventos de domínio via listeners:
 *   - OfferEventsListener   → enfileira deal-score + market-patterns
 *   - AlertEventsListener   → verifica alertas reativamente
 *   - AnalyticsEventsListener → persiste UserEvents
 *   - BillingEventsListener → reage a mudanças de plano
 */

import { Module } from '@nestjs/common';
import { BullModule } from '@nestjs/bullmq';
import { SentryModule } from '@sentry/nestjs/setup';
import { ScheduleModule } from '@nestjs/schedule';

// ── Infra ──────────────────────────────────────────────────────────────────
import { AppConfigModule }      from '../../backend/src/config/config.module';
import { EventsModule }         from '../../backend/src/shared/events/events.module';
import { PrismaModule }         from '../../backend/src/prisma/prisma.module';
import { RedisCacheModule }     from '../../backend/src/cache/cache.module';

// ── Módulos com processors e listeners ────────────────────────────────────
import { NotificationsModule }       from '../../backend/src/notifications/notifications.module';
import { AiOpsModule }               from '../../backend/src/ai-ops/ai-ops.module';
import { DealScoreModule }           from '../../backend/src/deal-score/deal-score.module';
import { ReviewIntelligenceModule }  from '../../backend/src/review-intelligence/review-intelligence.module';
import { MarketIntelligenceModule }  from '../../backend/src/market-intelligence/market-intelligence.module';
import { AnalyticsModule }           from '../../backend/src/analytics/analytics.module';
import { AlertsModule }              from '../../backend/src/alerts/alerts.module';
import { BillingModule }             from '../../backend/src/billing/billing.module';
import { PlansModule }               from '../../backend/src/plans/plans.module';
import { OffersModule }              from '../../backend/src/offers/offers.module';

// ── Scraper (processor principal) ─────────────────────────────────────────
import { CrawlerService }       from '../../backend/src/crawler/crawler.service';
import { ScraperHealthService } from '../../backend/src/crawler/scraper-health.service';
import { ScraperProcessor }     from '../../backend/src/crawler/queue/scraper.processor';
import { CleanupProcessor }     from '../../backend/src/crawler/queue/cleanup.processor';
import { CleanupQueueService }  from '../../backend/src/crawler/queue/cleanup-queue.service';
import {
  SCRAPER_QUEUE,
  SCRAPER_JOB_DEFAULTS,
} from '../../backend/src/crawler/queue/scraper.queue';
import {
  CLEANUP_QUEUE,
  CLEANUP_JOB_DEFAULTS,
} from '../../backend/src/shared/queues/queue.constants';

const WORKER_CONCURRENCY = parseInt(process.env.WORKER_CONCURRENCY ?? '5', 10);

@Module({
  imports: [
    SentryModule.forRoot(),
    ScheduleModule.forRoot(),

    // Config (validação Zod — deve ser o primeiro)
    AppConfigModule,

    // Event Bus global (EventEmitter2)
    EventsModule,

    // Redis — conexão compartilhada
    BullModule.forRootAsync({
      useFactory: () => ({
        connection: { url: process.env.REDIS_URL || 'redis://localhost:6379' },
      }),
    }),

    // Fila do scraper (registrada aqui pois os providers abaixo não usam CrawlerModule)
    BullModule.registerQueue(
      { name: SCRAPER_QUEUE, defaultJobOptions: SCRAPER_JOB_DEFAULTS },
      { name: CLEANUP_QUEUE, defaultJobOptions: CLEANUP_JOB_DEFAULTS },
    ),

    // Core
    PrismaModule,
    RedisCacheModule,

    // Módulos com processors (registram suas próprias filas internamente)
    NotificationsModule,       // NotificationProcessor + NotificationTriggerListener
    AiOpsModule,               // IncidentDetector → injetado em ScraperHealthService
    DealScoreModule,           // DealScoreProcessor + DealScoreQueueService
    ReviewIntelligenceModule,  // ReviewAnalyzerProcessor + ReviewQueueService
    MarketIntelligenceModule,  // MarketPatternsProcessor + MarketPatternsQueueService + Scheduler
    AnalyticsModule,           // AnalyticsEventsListener

    // Módulos com listeners de evento (sem processor, apenas reatividade)
    PlansModule,               // necessário para BillingModule
    BillingModule,             // BillingEventsListener
    AlertsModule,              // AlertEventsListener (verifica alertas em tempo real)
    OffersModule,              // OfferEventsListener (enfileira deal-score + market-patterns)
  ],

  providers: [
    // Scraper pipeline — injetado manualmente pois não usamos CrawlerModule completo
    CrawlerService,
    ScraperHealthService,
    { provide: ScraperProcessor, useClass: ScraperProcessor },

    // Cleanup
    CleanupProcessor,
    CleanupQueueService,
  ],
})
export class WorkerModule {}
