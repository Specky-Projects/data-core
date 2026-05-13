/**
 * scraper-queue.service.ts
 *
 * Facade para enfileirar jobs de scraping.
 * Isola o BullMQ Queue do resto da aplicação.
 */

import { InjectQueue } from '@nestjs/bullmq';
import { Injectable, Logger } from '@nestjs/common';
import { Queue } from 'bullmq';
import {
  SCRAPER_QUEUE,
  SCRAPER_JOB_DEFAULTS,
  PRIORITY,
  SyncOfferJobData,
} from './scraper.queue';

@Injectable()
export class ScraperQueueService {
  private readonly logger = new Logger(ScraperQueueService.name);

  constructor(
    @InjectQueue(SCRAPER_QUEUE) private readonly queue: Queue,
  ) {}

  /**
   * Enfileira sync de uma oferta individual.
   * Usado pelo scheduler adaptativo e pelo endpoint manual.
   */
  async enqueueSyncOffer(
    offerId: string,
    marketplace: string,
    productUrl: string,
    triggeredBy: SyncOfferJobData['triggeredBy'] = 'scheduler',
  ): Promise<void> {
    const priority = this.priorityFor(triggeredBy);

    await this.queue.add(
      'sync-offer',
      { offerId, marketplace, productUrl, triggeredBy } satisfies SyncOfferJobData,
      {
        ...SCRAPER_JOB_DEFAULTS,
        priority,
        jobId: `offer:${offerId}`, // deduplicação: evita enfileirar a mesma oferta duas vezes
      },
    );
  }

  /**
   * Enfileira um lote de ofertas de uma vez.
   * O BullMQ agrupa em uma transação Redis para eficiência.
   */
  async enqueueBatch(
    offers: Array<{ offerId: string; marketplace: string; productUrl: string; hasAlerts: boolean }>,
    triggeredBy: SyncOfferJobData['triggeredBy'] = 'scheduler',
  ): Promise<number> {
    const jobs = offers.map((o) => ({
      name: 'sync-offer' as const,
      data: {
        offerId:     o.offerId,
        marketplace: o.marketplace,
        productUrl:  o.productUrl,
        triggeredBy,
      } satisfies SyncOfferJobData,
      opts: {
        ...SCRAPER_JOB_DEFAULTS,
        priority: this.priorityFor(o.hasAlerts ? 'alert' : triggeredBy),
        jobId: `offer:${o.offerId}`,
      },
    }));

    const added = await this.queue.addBulk(jobs);
    this.logger.debug(`[queue] ${added.length} jobs enfileirados.`);
    return added.length;
  }

  // ── Métricas para o dashboard ──────────────────────────────────────────

  async getStats() {
    const [waiting, active, completed, failed, delayed] = await Promise.all([
      this.queue.getWaitingCount(),
      this.queue.getActiveCount(),
      this.queue.getCompletedCount(),
      this.queue.getFailedCount(),
      this.queue.getDelayedCount(),
    ]);
    return { waiting, active, completed, failed, delayed };
  }

  async getFailedJobs(limit = 20) {
    const jobs = await this.queue.getFailed(0, limit - 1);
    return jobs.map((j) => ({
      id:          j.id,
      offerId:     (j.data as SyncOfferJobData).offerId,
      marketplace: (j.data as SyncOfferJobData).marketplace,
      attempts:    j.attemptsMade,
      failedReason: j.failedReason,
      timestamp:   j.timestamp,
    }));
  }

  async retryFailed(): Promise<number> {
    const failed = await this.queue.getFailed(0, 99);
    await Promise.allSettled(failed.map((j) => j.retry()));
    this.logger.log(`[queue] ${failed.length} jobs re-enfileirados.`);
    return failed.length;
  }

  async clearCompleted(): Promise<void> {
    await this.queue.clean(0, 0, 'completed');
  }

  async pause(): Promise<void>  { await this.queue.pause(); }
  async resume(): Promise<void> { await this.queue.resume(); }
  async isPaused(): Promise<boolean> { return this.queue.isPaused(); }

  private priorityFor(triggeredBy: SyncOfferJobData['triggeredBy']): number {
    if (triggeredBy === 'manual') return PRIORITY.MANUAL;
    if (triggeredBy === 'alert') return PRIORITY.ALERT;
    return PRIORITY.SCHEDULE;
  }
}
