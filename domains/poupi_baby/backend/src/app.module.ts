import { Module } from '@nestjs/common';
import { ScheduleModule } from '@nestjs/schedule';
import { BullModule } from '@nestjs/bullmq';
import { SentryModule } from '@sentry/nestjs/setup';

// ── Config (deve ser primeiro — valida envs no bootstrap) ─────────────────────
import { AppConfigModule } from './config/config.module';

// ── Event Bus (global) ────────────────────────────────────────────────────────
import { EventsModule } from './shared/events/events.module';

// ── Core ──────────────────────────────────────────────────────────────────────
import { PrismaModule }       from './prisma/prisma.module';
import { AuthModule }         from './auth/auth.module';
import { RedisCacheModule }   from './cache/cache.module';
import { HealthModule }       from './health/health.module';

// ── Domínio ───────────────────────────────────────────────────────────────────
import { ProductsModule }     from './products/products.module';
import { MarketplacesModule } from './marketplaces/marketplaces.module';
import { OffersModule }       from './offers/offers.module';
import { PriceHistoryModule } from './price-history/price-history.module';
import { AlertsModule }       from './alerts/alerts.module';
import { NotificationsModule } from './notifications/notifications.module';
import { CrawlerModule }      from './crawler/crawler.module';

// ── Monetização ───────────────────────────────────────────────────────────────
import { PlansModule }        from './plans/plans.module';
import { AffiliateModule }    from './affiliate/affiliate.module';
import { PromotionsModule }   from './promotions/promotions.module';
import { BillingModule }      from './billing/billing.module';

// ── Intelligence Layer ────────────────────────────────────────────────────────
import { DealScoreModule }              from './deal-score/deal-score.module';
import { AiOpsModule }                  from './ai-ops/ai-ops.module';
import { ReviewIntelligenceModule }     from './review-intelligence/review-intelligence.module';
import { MarketIntelligenceModule }     from './market-intelligence/market-intelligence.module';

// ── Analytics ─────────────────────────────────────────────────────────────────
import { AnalyticsModule }              from './analytics/analytics.module';

// ── Admin ─────────────────────────────────────────────────────────────────────
import { AdminModule }                  from './admin/admin.module';

@Module({
  imports: [
    // ── Infra global (ordem importa) ─────────────────────────────────
    SentryModule.forRoot(),
    AppConfigModule,        // valida envs com Zod — falha fast se inválido
    EventsModule,           // EventBus global

    ScheduleModule.forRoot(),

    // BullMQ — usa process.env diretamente (antes da injeção do ConfigService)
    BullModule.forRootAsync({
      useFactory: () => ({
        connection: {
          url: process.env.REDIS_URL || 'redis://localhost:6379',
        },
      }),
    }),

    // ── Core ──────────────────────────────────────────────────────────
    PrismaModule,
    AuthModule,
    RedisCacheModule,       // Redis cache global
    HealthModule,

    // ── Domínio ───────────────────────────────────────────────────────
    ProductsModule,
    MarketplacesModule,
    OffersModule,
    PriceHistoryModule,
    AlertsModule,
    NotificationsModule,
    CrawlerModule,

    // ── Monetização ───────────────────────────────────────────────────
    PlansModule,
    AffiliateModule,
    PromotionsModule,
    BillingModule,

    // ── Intelligence Layer ────────────────────────────────────────────
    DealScoreModule,
    AiOpsModule,
    ReviewIntelligenceModule,
    MarketIntelligenceModule,

    // ── Analytics ─────────────────────────────────────────────────────────
    AnalyticsModule,

    // ── Admin ─────────────────────────────────────────────────────────────
    AdminModule,
  ],
})
export class AppModule {}
