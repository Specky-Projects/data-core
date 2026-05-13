import {
  BadRequestException,
  Controller,
  Delete,
  Get,
  Param,
  Post,
  Query,
  UseGuards,
} from '@nestjs/common';
import { AuthGuard } from '@nestjs/passport';
import { CrawlerService } from './crawler.service';
import { CrawlerScheduler } from './crawler.scheduler';
import { ScraperHealthService } from './scraper-health.service';
import { ScraperQueueService } from './queue/scraper-queue.service';
import { detectMarketplace } from './scrapers/registry';
import { AdminGuard } from '../common/admin.guard';

@UseGuards(AuthGuard('jwt'))
@Controller('crawler')
export class CrawlerController {
  constructor(
    private readonly crawlerService: CrawlerService,
    private readonly scheduler: CrawlerScheduler,
    private readonly healthService: ScraperHealthService,
    private readonly queueService: ScraperQueueService,
  ) {}

  // ── Scraping manual ───────────────────────────────────────────────────────

  /** GET /crawler/scrape?url=... */
  @Get('scrape')
  async crawl(@Query('url') url: string) {
    if (!url) throw new BadRequestException('URL é obrigatória');
    let parsed: URL;
    try { parsed = new URL(url); } catch { throw new BadRequestException('URL inválida'); }
    if (!['https:', 'http:'].includes(parsed.protocol)) throw new BadRequestException('Protocolo não permitido');
    if (!detectMarketplace(url)) throw new BadRequestException(`Marketplace não suportado: ${parsed.hostname}`);
    return this.crawlerService.crawlUrl(url);
  }

  /** GET /crawler/amazon?url=... — retrocompatível */
  @Get('amazon')
  crawlAmazon(@Query('url') url: string) {
    return this.crawl(url);
  }

  /** GET /crawler/sync/:offerId — sync direto (sem fila) */
  @Get('sync/:offerId')
  syncOffer(@Param('offerId') offerId: string) {
    return this.crawlerService.syncOffer(offerId);
  }

  /** POST /crawler/sync — enfileira sync de todas as ofertas com prioridade máxima */
  @Post('sync')
  async runFullSync() {
    return this.scheduler.runNow();
  }

  /** POST /crawler/sync/:offerId — enfileira sync manual de uma oferta */
  @Post('sync/:offerId')
  async enqueueSync(@Param('offerId') offerId: string) {
    const offer = await this.crawlerService.getOfferForQueue(offerId);
    if (!offer) throw new BadRequestException(`Oferta não encontrada: ${offerId}`);
    await this.queueService.enqueueSyncOffer(
      offer.id,
      offer.marketplace,
      offer.productUrl,
      'manual',
    );
    return { enqueued: true, offerId };
  }

  // ── Health e métricas (P1 + P2) — admin only ─────────────────────────────

  /** GET /crawler/health — todos os scrapers ordenados por successRate */
  @UseGuards(AdminGuard)
  @Get('health')
  getHealth() {
    return this.healthService.getAll();
  }

  /** GET /crawler/health/ranking — marketplace ranking compacto */
  @UseGuards(AdminGuard)
  @Get('health/ranking')
  getRanking() {
    return this.healthService.getRanking();
  }

  /** GET /crawler/health/:marketplace */
  @UseGuards(AdminGuard)
  @Get('health/:marketplace')
  getHealthOne(@Param('marketplace') marketplace: string) {
    return this.healthService.getOne(marketplace);
  }

  /** GET /crawler/metrics/:marketplace?days=7 — timeline por hora */
  @UseGuards(AdminGuard)
  @Get('metrics/:marketplace')
  getTimeline(
    @Param('marketplace') marketplace: string,
    @Query('days') days?: string,
  ) {
    return this.healthService.getTimeline(marketplace, days ? Number(days) : undefined);
  }

  /** GET /crawler/metrics/:marketplace/failures?days=30 — breakdown de erros */
  @UseGuards(AdminGuard)
  @Get('metrics/:marketplace/failures')
  getFailureReasons(
    @Param('marketplace') marketplace: string,
    @Query('days') days?: string,
  ) {
    return this.healthService.getFailureReasons(marketplace, days ? Number(days) : undefined);
  }

  // ── Queue management — admin only ─────────────────────────────────────────

  /** GET /crawler/queue/stats — métricas da fila BullMQ */
  @UseGuards(AdminGuard)
  @Get('queue/stats')
  getQueueStats() {
    return this.queueService.getStats();
  }

  /** GET /crawler/queue/failed — jobs falhos recentes */
  @UseGuards(AdminGuard)
  @Get('queue/failed')
  getFailedJobs(@Query('limit') limit?: string) {
    return this.queueService.getFailedJobs(limit ? Number(limit) : 20);
  }

  /** POST /crawler/queue/retry — re-enfileira todos os jobs falhos */
  @UseGuards(AdminGuard)
  @Post('queue/retry')
  retryFailed() {
    return this.queueService.retryFailed().then((count) => ({ retried: count }));
  }

  /** DELETE /crawler/queue/completed — limpa jobs completos */
  @UseGuards(AdminGuard)
  @Delete('queue/completed')
  clearCompleted() {
    return this.queueService.clearCompleted().then(() => ({ cleared: true }));
  }

  /** POST /crawler/queue/pause — pausa o worker */
  @UseGuards(AdminGuard)
  @Post('queue/pause')
  pauseQueue() {
    return this.queueService.pause().then(() => ({ paused: true }));
  }

  /** POST /crawler/queue/resume — retoma o worker */
  @UseGuards(AdminGuard)
  @Post('queue/resume')
  resumeQueue() {
    return this.queueService.resume().then(() => ({ resumed: true }));
  }
}
