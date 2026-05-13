import { Module } from '@nestjs/common';
import { BullModule } from '@nestjs/bullmq';
import { PrismaModule } from '../prisma/prisma.module';
import { DealScoreService }         from './deal-score.service';
import { DealScoreController }      from './deal-score.controller';
import { DealScoreProcessor }       from './queue/deal-score.processor';
import { DealScoreQueueService }    from './queue/deal-score-queue.service';
import {
  DEAL_SCORE_QUEUE,
  DEAL_SCORE_JOB_DEFAULTS,
} from '../shared/queues/queue.constants';

@Module({
  imports: [
    PrismaModule,
    BullModule.registerQueue({
      name:              DEAL_SCORE_QUEUE,
      defaultJobOptions: DEAL_SCORE_JOB_DEFAULTS,
    }),
  ],
  providers:   [DealScoreService, DealScoreProcessor, DealScoreQueueService],
  controllers: [DealScoreController],
  exports:     [DealScoreService, DealScoreQueueService],
})
export class DealScoreModule {}
