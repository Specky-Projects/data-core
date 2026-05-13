import { Processor, WorkerHost } from '@nestjs/bullmq';
import { Logger } from '@nestjs/common';
import { Job } from 'bullmq';
import { MarketIntelligenceService } from '../market-intelligence.service';
import {
  MARKET_PATTERNS_QUEUE,
  MARKET_PATTERNS_JOB,
  MarketPatternsJobData,
} from '../../shared/queues/queue.constants';

@Processor(MARKET_PATTERNS_QUEUE)
export class MarketPatternsProcessor extends WorkerHost {
  private readonly logger = new Logger(MarketPatternsProcessor.name);

  constructor(private readonly service: MarketIntelligenceService) {
    super();
  }

  async process(job: Job<MarketPatternsJobData>): Promise<void> {
    if (job.name !== MARKET_PATTERNS_JOB) return;

    const { productId, marketplace, reason } = job.data;
    this.logger.debug(
      `[market-patterns] Calculando padrões — ${marketplace}/${productId} reason=${reason}`,
    );

    try {
      const result = await this.service.analyzeProduct(productId, marketplace);

      if (result) {
        this.logger.debug(
          `[market-patterns] Padrões calculados — ${marketplace}/${productId}: ` +
          `${result.trendDirection} (strength=${result.trendStrength.toFixed(2)})`,
        );
      }
    } catch (err: any) {
      this.logger.error(`[market-patterns] Erro no job ${job.id}: ${err.message}`);
      throw err;
    }
  }
}
