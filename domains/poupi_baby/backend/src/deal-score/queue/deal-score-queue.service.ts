import { Injectable, Logger } from '@nestjs/common';
import { InjectQueue } from '@nestjs/bullmq';
import { Queue } from 'bullmq';
import {
  DEAL_SCORE_QUEUE,
  DEAL_SCORE_JOB,
  DealScoreJobData,
} from '../../shared/queues/queue.constants';

@Injectable()
export class DealScoreQueueService {
  private readonly logger = new Logger(DealScoreQueueService.name);

  constructor(
    @InjectQueue(DEAL_SCORE_QUEUE) private readonly queue: Queue,
  ) {}

  async enqueue(data: DealScoreJobData, priority?: number): Promise<void> {
    await this.queue.add(DEAL_SCORE_JOB, data, {
      jobId:    `deal-score:${data.offerId}`,  // deduplicação por offerId
      priority: priority ?? 10,
    });
    this.logger.debug(`[deal-score-queue] Enqueued offerId=${data.offerId} reason=${data.reason}`);
  }

  /** Enfileira vários offers de uma vez (ex: após scraping em massa) */
  async enqueueBulk(items: DealScoreJobData[]): Promise<void> {
    if (items.length === 0) return;
    const jobs = items.map((data) => ({
      name: DEAL_SCORE_JOB,
      data,
      opts: { jobId: `deal-score:${data.offerId}`, priority: 20 },
    }));
    await this.queue.addBulk(jobs);
    this.logger.debug(`[deal-score-queue] Enqueued bulk: ${items.length} jobs`);
  }
}
