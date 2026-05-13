import { Injectable, Logger } from '@nestjs/common';
import { InjectQueue } from '@nestjs/bullmq';
import { Queue } from 'bullmq';
import {
  REVIEW_ANALYZER_QUEUE,
  REVIEW_ANALYZER_JOB,
  ReviewAnalyzerJobData,
} from '../../shared/queues/queue.constants';

@Injectable()
export class ReviewQueueService {
  private readonly logger = new Logger(ReviewQueueService.name);

  constructor(
    @InjectQueue(REVIEW_ANALYZER_QUEUE) private readonly queue: Queue,
  ) {}

  async enqueue(data: ReviewAnalyzerJobData): Promise<void> {
    const jobId = `review:${data.productId}:${data.marketplace}`;
    await this.queue.add(REVIEW_ANALYZER_JOB, data, {
      jobId,          // deduplicação por produto+marketplace
      priority: 20,
    });
    this.logger.debug(
      `[review-queue] Enqueued ${data.marketplace}/${data.productId} source=${data.source}`,
    );
  }
}
