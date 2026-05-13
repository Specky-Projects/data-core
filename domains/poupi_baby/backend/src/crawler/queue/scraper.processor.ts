/**
 * scraper.processor.ts
 *
 * Worker BullMQ que processa jobs de scraping da fila `scraper`.
 *
 * - Concorrência configurável por instância (default: 5)
 * - Por marketplace: semáforo simples para limitar execuções paralelas
 *   (Amazon: 1, ML: 4, Magalu/Kabum/Drogasil: 2)
 * - Falha permanente (4 tentativas) → registra no ScraperHealth como SCRAPER_FAILED
 * - Integra com CrawlerService (mesma lógica de sincronização)
 */

import { Processor, WorkerHost, OnWorkerEvent } from '@nestjs/bullmq';
import { Logger } from '@nestjs/common';
import { Job } from 'bullmq';
import { CrawlerService } from '../crawler.service';
import { ScraperHealthService } from '../scraper-health.service';
import {
  SCRAPER_QUEUE,
  SyncOfferJobData,
  ScraperJobData,
} from './scraper.queue';

// Limites de concorrência por marketplace (evita ban simultâneo)
// Amazon é mais agressivo com rate-limit → 1
// ML permite mais paralelas → 4
// Magalu/Kabum/Drogasil → 2
const MARKETPLACE_CONCURRENCY: Record<string, number> = {
  amazon:       1,
  mercadolivre: 2,
  kabum:        1,
  magalu:       1,
  drogasil:     1,
  drogaraia:    1,
  paguemenos:   1,
  default:      1,
};

@Processor(SCRAPER_QUEUE, { concurrency: 3 })
export class ScraperProcessor extends WorkerHost {
  private readonly logger = new Logger(ScraperProcessor.name);

  // Semáforo de concorrência por marketplace
  private readonly inFlight = new Map<string, number>();

  constructor(
    private readonly crawlerService: CrawlerService,
    private readonly healthService: ScraperHealthService,
  ) {
    super();
  }

  async process(job: Job<ScraperJobData>): Promise<unknown> {
    // Suporta apenas SyncOfferJobData por enquanto
    // (SyncAllJobData é despachado diretamente pelo scheduler)
    const data = job.data as SyncOfferJobData;
    if (!data.offerId) {
      this.logger.warn(`[queue] Job ${job.id} sem offerId — ignorado.`);
      return { skipped: true };
    }

    const marketplace = data.marketplace ?? 'unknown';
    const maxConcurrent = MARKETPLACE_CONCURRENCY[marketplace] ?? MARKETPLACE_CONCURRENCY.default;

    // Aguarda slot de concorrência do marketplace (spin-wait leve)
    await this.waitForSlot(marketplace, maxConcurrent);

    this.logger.debug(
      `[queue] Processando oferta ${data.offerId} (${marketplace}, tentativa ${job.attemptsMade + 1})`,
    );

    try {
      const result = await this.crawlerService.syncOffer(data.offerId, {
        attempt: job.attemptsMade + 1,
        triggeredBy: data.triggeredBy,
      }) as { success?: boolean; error?: string };
      if (result?.success === false) {
        throw new Error(result.error ?? 'scraping_failed');
      }
      return result;
    } finally {
      this.releaseSlot(marketplace);
    }
  }

  // ── Semáforo por marketplace ────────────────────────────────────────────

  private async waitForSlot(marketplace: string, max: number): Promise<void> {
    const pollMs = 200;
    const timeoutMs = 30_000;
    const start = Date.now();

    while (true) {
      const current = this.inFlight.get(marketplace) ?? 0;
      if (current < max) {
        this.inFlight.set(marketplace, current + 1);
        return;
      }
      if (Date.now() - start > timeoutMs) {
        // Timeout — prossegue mesmo assim (melhor processar que travar)
        this.logger.warn(`[queue] Semáforo timeout para ${marketplace} — prosseguindo.`);
        return;
      }
      await new Promise((r) => setTimeout(r, pollMs));
    }
  }

  private releaseSlot(marketplace: string): void {
    const current = this.inFlight.get(marketplace) ?? 1;
    this.inFlight.set(marketplace, Math.max(0, current - 1));
  }

  // ── Eventos do worker ───────────────────────────────────────────────────

  @OnWorkerEvent('completed')
  onCompleted(job: Job<ScraperJobData>) {
    const data = job.data as SyncOfferJobData;
    if (data.offerId) {
      this.logger.debug(`[queue] Job ${job.id} completo: oferta ${data.offerId}`);
    }
  }

  @OnWorkerEvent('failed')
  async onFailed(job: Job<ScraperJobData> | undefined, err: Error) {
    if (!job) return;
    const data = job.data as SyncOfferJobData;
    const isLastAttempt = job.attemptsMade >= (job.opts.attempts ?? 4);

    this.logger.error(
      `[queue] Job ${job.id} falhou (tentativa ${job.attemptsMade}/${job.opts.attempts}): ${err.message}`,
    );

    if (isLastAttempt && data.marketplace) {
      // Job esgotou todas as tentativas — registra falha permanente no health
      this.logger.warn(
        `[queue] Oferta ${data.offerId} esgotou tentativas — registrando no health.`,
      );
      await this.healthService.record(
        data.marketplace,
        false,
        0,
        `DLQ: ${err.message}`,
      ).catch(() => { /* não propaga erro de health em falha crítica */ });
    }
  }

  @OnWorkerEvent('stalled')
  onStalled(jobId: string) {
    this.logger.warn(`[queue] Job ${jobId} travou (stalled) — será re-enfileirado.`);
  }
}
