import { Injectable, Logger } from '@nestjs/common';
import { InjectQueue } from '@nestjs/bullmq';
import { Queue } from 'bullmq';
import {
  MARKET_PATTERNS_QUEUE,
  MARKET_PATTERNS_JOB,
  MarketPatternsJobData,
} from '../../shared/queues/queue.constants';

@Injectable()
export class MarketPatternsQueueService {
  private readonly logger = new Logger(MarketPatternsQueueService.name);

  constructor(
    @InjectQueue(MARKET_PATTERNS_QUEUE) private readonly queue: Queue,
  ) {}

  async enqueue(data: MarketPatternsJobData): Promise<void> {
    const jobId = `market-patterns:${data.productId}:${data.marketplace}`;
    await this.queue.add(MARKET_PATTERNS_JOB, data, {
      jobId,
      priority: 30,
      // delay de 5s para agrupar múltiplas atualizações do mesmo produto
      delay: 5_000,
    });
    this.logger.debug(
      `[market-patterns-queue] Enqueued ${data.marketplace}/${data.productId} reason=${data.reason}`,
    );
  }
}
