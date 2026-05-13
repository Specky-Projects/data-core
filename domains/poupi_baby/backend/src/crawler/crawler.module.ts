import { Module } from '@nestjs/common';
import { BullModule } from '@nestjs/bullmq';
import { PrismaModule } from '../prisma/prisma.module';
import { AiOpsModule } from '../ai-ops/ai-ops.module';
import { CrawlerController } from './crawler.controller';
import { CrawlerService } from './crawler.service';
import { CrawlerScheduler } from './crawler.scheduler';
import { ScraperHealthService } from './scraper-health.service';
import { ScraperProcessor } from './queue/scraper.processor';
import { ScraperQueueService } from './queue/scraper-queue.service';
import { CleanupProcessor } from './queue/cleanup.processor';
import { CleanupQueueService } from './queue/cleanup-queue.service';
import { DrogasilSourceAdapter } from './sources/adapters/drogasil.adapter';
import { DrogaRaiaSourceAdapter } from './sources/adapters/droga-raia.adapter';
import { HtmlSnapshotService } from './sources/html-snapshot.service';
import { ScraperCircuitBreakerService } from './sources/circuit-breaker.service';
import { BrowserSessionService } from './sources/browser-session.service';
import { ProxyPoolService } from './sources/proxy-pool.service';
import { ScraperDomainMetricsService } from './sources/domain-metrics.service';
import { SourceAdapterRegistry } from './sources/source-adapter.registry';
import { SCRAPER_QUEUE, SCRAPER_JOB_DEFAULTS } from './queue/scraper.queue';
import {
  CLEANUP_QUEUE,
  CLEANUP_JOB_DEFAULTS,
} from '../shared/queues/queue.constants';

@Module({
  imports: [
    PrismaModule,
    AiOpsModule,
    BullModule.registerQueue(
      { name: SCRAPER_QUEUE, defaultJobOptions: SCRAPER_JOB_DEFAULTS },
      { name: CLEANUP_QUEUE, defaultJobOptions: CLEANUP_JOB_DEFAULTS },
    ),
  ],
  controllers: [CrawlerController],
  providers: [
    CrawlerService,
    CrawlerScheduler,
    ScraperHealthService,
    ScraperProcessor,
    ScraperQueueService,
    CleanupProcessor,
    CleanupQueueService,
    DrogasilSourceAdapter,
    DrogaRaiaSourceAdapter,
    HtmlSnapshotService,
    ScraperCircuitBreakerService,
    BrowserSessionService,
    ProxyPoolService,
    ScraperDomainMetricsService,
    SourceAdapterRegistry,
  ],
  exports: [
    CrawlerService,
    ScraperHealthService,
    ScraperQueueService,
    ProxyPoolService,
    ScraperDomainMetricsService,
    ScraperCircuitBreakerService,
  ],
})
export class CrawlerModule {}
