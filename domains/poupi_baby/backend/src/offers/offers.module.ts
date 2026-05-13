import { Module } from '@nestjs/common';
import { BullModule } from '@nestjs/bullmq';
import { PrismaModule } from '../prisma/prisma.module';
import { DealScoreModule } from '../deal-score/deal-score.module';
import { MarketIntelligenceModule } from '../market-intelligence/market-intelligence.module';
import { OffersController } from './offers.controller';
import { OffersService } from './offers.service';
import { OfferEventsListener } from './listeners/offer-events.listener';
import {
  DEAL_SCORE_QUEUE,
  DEAL_SCORE_JOB_DEFAULTS,
  MARKET_PATTERNS_QUEUE,
  MARKET_PATTERNS_JOB_DEFAULTS,
} from '../shared/queues/queue.constants';

@Module({
  imports: [
    PrismaModule,
    DealScoreModule,
    MarketIntelligenceModule,
    BullModule.registerQueue(
      { name: DEAL_SCORE_QUEUE,      defaultJobOptions: DEAL_SCORE_JOB_DEFAULTS },
      { name: MARKET_PATTERNS_QUEUE, defaultJobOptions: MARKET_PATTERNS_JOB_DEFAULTS },
    ),
  ],
  controllers: [OffersController],
  providers:   [OffersService, OfferEventsListener],
  exports:     [OffersService],
})
export class OffersModule {}