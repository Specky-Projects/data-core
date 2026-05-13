import { Module } from '@nestjs/common';
import { BullModule } from '@nestjs/bullmq';
import { PrismaModule } from '../prisma/prisma.module';
import { MarketIntelligenceService }    from './market-intelligence.service';
import { MarketIntelligenceController } from './market-intelligence.controller';
import { MarketIntelligenceScheduler }  from './market-intelligence.scheduler';
import { MarketPatternsProcessor }      from './queue/market-patterns.processor';
import { MarketPatternsQueueService }   from './queue/market-patterns-queue.service';
import {
  MARKET_PATTERNS_QUEUE,
  MARKET_PATTERNS_JOB_DEFAULTS,
} from '../shared/queues/queue.constants';

@Module({
  imports: [
    PrismaModule,
    BullModule.registerQueue({
      name:              MARKET_PATTERNS_QUEUE,
      defaultJobOptions: MARKET_PATTERNS_JOB_DEFAULTS,
    }),
  ],
  controllers: [MarketIntelligenceController],
  providers:   [
    MarketIntelligenceService,
    MarketIntelligenceScheduler,
    MarketPatternsProcessor,
    MarketPatternsQueueService,
  ],
  exports: [MarketIntelligenceService, MarketPatternsQueueService],
})
export class MarketIntelligenceModule {}
