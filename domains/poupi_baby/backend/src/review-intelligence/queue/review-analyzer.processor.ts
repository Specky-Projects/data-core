import { Processor, WorkerHost } from '@nestjs/bullmq';
import { Logger } from '@nestjs/common';
import { Job } from 'bullmq';
import { ReviewIntelligenceService } from '../review-intelligence.service';
import {
  REVIEW_ANALYZER_QUEUE,
  REVIEW_ANALYZER_JOB,
  ReviewAnalyzerJobData,
} from '../../shared/queues/queue.constants';

@Processor(REVIEW_ANALYZER_QUEUE)
export class ReviewAnalyzerProcessor extends WorkerHost {
  private readonly logger = new Logger(ReviewAnalyzerProcessor.name);

  constructor(private readonly service: ReviewIntelligenceService) {
    super();
  }

  async process(job: Job<ReviewAnalyzerJobData>): Promise<void> {
    if (job.name !== REVIEW_ANALYZER_JOB) return;

    const { productId, marketplace, source, ...reviewData } = job.data;
    this.logger.debug(
      `[review-analyzer] Processando reviews — ${marketplace}/${productId} source=${source}`,
    );

    try {
      const result = await this.service.processReviews({
        productId,
        marketplace,
        ...reviewData,
      });

      this.logger.debug(
        `[review-analyzer] Trust Score calculado — ${marketplace}/${productId}: ${result.trustScore} (${result.trustLabel})`,
      );
    } catch (err: any) {
      this.logger.error(
        `[review-analyzer] Erro no job ${job.id}: ${err.message}`,
      );
      throw err;
    }
  }
}
