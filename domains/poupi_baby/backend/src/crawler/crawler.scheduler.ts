/**
 * crawler.scheduler.ts
 *
 * Scheduling adaptativo com BullMQ — P3
 *
 * O cron de 1h decide QUAIS ofertas enfileirar (intervalo adaptativo),
 * enquanto o BullMQ Worker decide QUANDO e COMO processar cada job
 * (concorrência, retry, backoff, DLQ).
 *
 * Intervalo de sync por oferta:
 *
 *   Produto com alertas ativos (usuário esperando queda)  →  2h   [critico]
 *   Marketplace saudável (successRate >= 80%)             →  6h   [normal]
 *   Marketplace instável  (successRate 40–79%)            →  24h  [back-off]
 *   Marketplace crítico   (successRate < 40%)             →  48h  [quarentena leve]
 */

import { Injectable, Logger } from '@nestjs/common';
import { Cron } from '@nestjs/schedule';
import { CrawlerService } from './crawler.service';
import { ScraperHealthService } from './scraper-health.service';
import { ScraperQueueService } from './queue/scraper-queue.service';
import { detectStoreName } from './scrapers/registry';

// Intervalos em ms
const INTERVAL = {
  CRITICAL_ALERTS: 2  * 3600_000,  // produto com alertas ativos
  HEALTHY:         6  * 3600_000,  // scraper > 80% sucesso
  UNSTABLE:        24 * 3600_000,  // scraper 40-80%
  STRUGGLING:      48 * 3600_000,  // scraper < 40%
} as const;

const CALIBRATION_MODE = process.env.SCRAPER_CALIBRATION_MODE === 'true';
const CALIBRATION_MAX_PER_DOMAIN = Number(process.env.SCRAPER_CALIBRATION_MAX_PER_DOMAIN ?? 5);

function computeInterval(
  successRate: number | undefined,
  hasActiveAlerts: boolean,
): number {
  if (hasActiveAlerts)                                     return INTERVAL.CRITICAL_ALERTS;
  if (successRate === undefined || successRate >= 80)      return INTERVAL.HEALTHY;
  if (successRate >= 40)                                   return INTERVAL.UNSTABLE;
  return INTERVAL.STRUGGLING;
}

@Injectable()
export class CrawlerScheduler {
  private readonly logger = new Logger(CrawlerScheduler.name);
  private isEnqueuing = false;

  constructor(
    private readonly crawlerService: CrawlerService,
    private readonly healthService: ScraperHealthService,
    private readonly queueService: ScraperQueueService,
  ) {}

  // Cron a cada hora — decide quais ofertas enfileirar
  @Cron('0 0 * * * *')
  async handleCron() {
    if (this.isEnqueuing) {
      this.logger.warn('Enfileiramento anterior ainda em andamento — pulando.');
      return;
    }

    this.isEnqueuing = true;
    const start = Date.now();

    try {
      this.logger.log('[scheduler] Iniciando ciclo adaptativo...');

      const [offers, healthMap] = await Promise.all([
        this.crawlerService.getActiveOffers(),
        this.crawlerService.getHealthMap(),
      ]);

      const now = Date.now();
      const due: Array<{
        offerId: string;
        marketplace: string;
        productUrl: string;
        hasAlerts: boolean;
      }> = [];
      let skipped = 0;

      for (const offer of offers) {
        const marketplaceName = detectStoreName(offer.productUrl) ?? (offer as any).marketplace?.name ?? '';
        const health = healthMap.get(marketplaceName);
        const hasAlerts = (offer as any)._hasAlerts ?? false;
        const interval = computeInterval(health?.successRate, hasAlerts);
        const age = now - new Date(offer.lastCheckedAt).getTime();

        if (age >= interval) {
          due.push({
            offerId:     offer.id,
            marketplace: marketplaceName,
            productUrl:  offer.productUrl,
            hasAlerts,
          });
        } else {
          skipped++;
        }
      }

      if (due.length === 0) {
        this.logger.log(`[scheduler] Nenhuma oferta devida (${skipped} aguardando intervalo).`);
        return;
      }

      const jobs = CALIBRATION_MODE ? this.applyCalibrationLimit(due) : due;
      if (CALIBRATION_MODE) {
        this.logger.warn(
          `[scheduler] modo calibracao ativo: ${jobs.length}/${due.length} jobs mantidos, max ${CALIBRATION_MAX_PER_DOMAIN} por dominio.`,
        );
      }

      // Enfileira em batch — BullMQ deduplica pelo jobId offer:<id>
      const enqueued = await this.queueService.enqueueBatch(jobs, 'scheduler');

      const elapsed = ((Date.now() - start) / 1000).toFixed(1);
      this.logger.log(
        `[scheduler] ${elapsed}s — ${enqueued} jobs enfileirados, ${skipped} aguardando.`,
      );

    } catch (err) {
      this.logger.error('[scheduler] Erro fatal:', err);
    } finally {
      this.isEnqueuing = false;
    }
  }

  // Limpeza semanal de métricas antigas
  @Cron('0 0 3 * * 0')  // domingo 03:00
  async pruneMetrics() {
    const count = await this.healthService.pruneOldMetrics();
    this.logger.log(`[scheduler] Limpeza: ${count} métricas removidas.`);
  }

  /**
   * Sync forçado via POST /crawler/sync
   * Enfileira TODAS as ofertas ativas com prioridade MANUAL,
   * sem verificar intervalos (força re-sync completo).
   */
  async runNow(): Promise<{ enqueued: number }> {
    this.logger.log('[scheduler] Sync forçado iniciado.');
    const offers = await this.crawlerService.getActiveOffers();

    const enqueued = await this.queueService.enqueueBatch(
      offers.map((o) => ({
        offerId:     o.id,
        marketplace: detectStoreName(o.productUrl) ?? (o as any).marketplace?.name ?? '',
        productUrl:  o.productUrl,
        hasAlerts:   false, // força MANUAL priority via triggeredBy
      })),
      'manual',
    );

    this.logger.log(`[scheduler] Sync forçado: ${enqueued} jobs enfileirados.`);
    return { enqueued };
  }

  private applyCalibrationLimit<T extends { productUrl: string }>(jobs: T[]): T[] {
    const counts = new Map<string, number>();
    return jobs.filter((job) => {
      const domain = this.domainOf(job.productUrl);
      const current = counts.get(domain) ?? 0;
      if (current >= CALIBRATION_MAX_PER_DOMAIN) return false;
      counts.set(domain, current + 1);
      return true;
    });
  }

  private domainOf(url: string): string {
    try {
      return new URL(url).hostname.replace(/^www\./, '');
    } catch {
      return 'unknown';
    }
  }
}
