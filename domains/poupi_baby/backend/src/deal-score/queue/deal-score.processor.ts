import { Processor, WorkerHost } from '@nestjs/bullmq';
import { Logger } from '@nestjs/common';
import { Job } from 'bullmq';
import { DealScoreService } from '../deal-score.service';
import { EventBusService } from '../../shared/events/event-bus.service';
import { DOMAIN_EVENTS } from '../../shared/events/domain-events';
import {
  DEAL_SCORE_QUEUE,
  DEAL_SCORE_JOB,
  DealScoreJobData,
} from '../../shared/queues/queue.constants';

@Processor(DEAL_SCORE_QUEUE)
export class DealScoreProcessor extends WorkerHost {
  private readonly logger = new Logger(DealScoreProcessor.name);

  constructor(
    private readonly dealScoreService: DealScoreService,
    private readonly eventBus:         EventBusService,
  ) {
    super();
  }

  async process(job: Job<DealScoreJobData>): Promise<void> {
    if (job.name !== DEAL_SCORE_JOB) return;

    const { offerId, productId, reason } = job.data;
    this.logger.debug(`[deal-score] Calculando score — offerId=${offerId} reason=${reason}`);

    try {
      const result = await this.dealScoreService.calculate(offerId);

      if (!result) {
        this.logger.debug(`[deal-score] Dados insuficientes para offerId=${offerId} — job ignorado`);
        return;
      }

      // Emite evento de score calculado
      this.eventBus.emit(DOMAIN_EVENTS.DEAL_SCORE_CALCULATED, {
        offerId,
        productId,
        score: result.score,
        label: result.label,
      });

      // Score alto → emite evento especial para disparo de notificação
      if (result.score >= 75) {
        this.eventBus.emit(DOMAIN_EVENTS.DEAL_SCORE_HIGH, {
          offerId,
          productId,
          score:        result.score,
          label:        result.label,
          currentPrice: result.context.currentPrice,
          avg90d:       result.context.avg90d,
          discountVsAvg: result.context.discountVsAvg,
        });
      }

      this.logger.debug(
        `[deal-score] Score calculado — offerId=${offerId} score=${result.score} (${result.label})`,
      );
    } catch (err: any) {
      this.logger.error(`[deal-score] Erro no job ${job.id}: ${err.message}`);
      throw err; // BullMQ faz retry
    }
  }
}
