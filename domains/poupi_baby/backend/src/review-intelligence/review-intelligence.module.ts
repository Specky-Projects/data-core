import { Module } from '@nestjs/common';
import { BullModule } from '@nestjs/bullmq';
import { PrismaModule } from '../prisma/prisma.module';
import { ReviewIntelligenceService }    from './review-intelligence.service';
import { ReviewIntelligenceController } from './review-intelligence.controller';
import { ReviewAnalyzerProcessor }      from './queue/review-analyzer.processor';
import { ReviewQueueService }           from './queue/review-queue.service';
import {
  REVIEW_ANALYZER_QUEUE,
  REVIEW_ANALYZER_JOB_DEFAULTS,
} from '../shared/queues/queue.constants';

@Module({
  imports: [
    PrismaModule,
    BullModule.registerQueue({
      name:              REVIEW_ANALYZER_QUEUE,
      defaultJobOptions: REVIEW_ANALYZER_JOB_DEFAULTS,
    }),
  ],
  controllers: [ReviewIntelligenceController],
  providers:   [
    ReviewIntelligenceService,
    ReviewAnalyzerProcessor,
    ReviewQueueService,
  ],
  exports: [ReviewIntelligenceService, ReviewQueueService],
})
export class ReviewIntelligenceModule {}
