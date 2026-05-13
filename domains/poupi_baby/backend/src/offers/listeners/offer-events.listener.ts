/**
 * offer-events.listener.ts
 *
 * Reage a eventos de preço para disparar:
 *   - Recalculo de deal score (fila deal-score)
 *   - Recalculo de market patterns (fila market-patterns)
 *   - Check de alertas (AlertsService)
 */

import { Injectable, Logger } from '@nestjs/common';
import { OnEvent } from '@nestjs/event-emitter';
import { DealScoreQueueService } from '../../deal-score/queue/deal-score-queue.service';
import { MarketPatternsQueueService } from '../../market-intelligence/queue/market-patterns-queue.service';
import { DOMAIN_EVENTS } from '../../shared/events/domain-events';
import type { OfferPriceUpdatedPayload } from '../../shared/events/domain-events';

@Injectable()
export class OfferEventsListener {
  private readonly logger = new Logger(OfferEventsListener.name);

  constructor(
    private readonly dealScoreQueue:     DealScoreQueueService,
    private readonly marketPatternsQueue: MarketPatternsQueueService,
  ) {}

  /**
   * Preço atualizado → recalcula deal score + market patterns em background.
   * Fire-and-forget: erros são logados, nunca propagados para o scraper.
   */
  @OnEvent(DOMAIN_EVENTS.OFFER_PRICE_UPDATED)
  async handlePriceUpdated(event: { payload: OfferPriceUpdatedPayload }): Promise<void> {
    const { offerId, productId, marketplace } = event.payload;

    try {
      await Promise.all([
        this.dealScoreQueue.enqueue({ offerId, productId, reason: 'price_updated' }),
        this.marketPatternsQueue.enqueue({ productId, marketplace, reason: 'price_updated' }),
      ]);

      this.logger.debug(
        `[offer-listener] Jobs enqueued após price_updated — offerId=${offerId}`,
      );
    } catch (err: any) {
      this.logger.error(`[offer-listener] Falha ao enfileirar jobs: ${err.message}`);
    }
  }

  /** Oferta voltou ao estoque → recalcula deal score (disponibilidade afeta score) */
  @OnEvent(DOMAIN_EVENTS.OFFER_BACK_IN_STOCK)
  async handleBackInStock(event: { payload: OfferPriceUpdatedPayload }): Promise<void> {
    const { offerId, productId } = event.payload;

    try {
      await this.dealScoreQueue.enqueue(
        { offerId, productId, reason: 'price_updated' },
        5, // prioridade alta
      );
    } catch (err: any) {
      this.logger.error(`[offer-listener] Falha ao enfileirar back-in-stock job: ${err.message}`);
    }
  }
}
