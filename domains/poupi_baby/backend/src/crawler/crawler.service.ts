/**
 * crawler.service.ts
 *
 * Orquestra o ciclo completo de scraping:
 *   1. Cache determinístico por store:externalId
 *   2. Rate limit por domínio
 *   3. Health check — pula scrapers desativados
 *   4. Scraping + medição de latência
 *   5. Registra health com errorType tipado
 *   6. Grava PriceHistory se preço mudou
 *   7. Emite eventos de domínio (price_updated, back_in_stock, out_of_stock)
 *      → AlertEventsListener verifica alertas
 *      → DealScoreProcessor recalcula deal score
 *      → MarketPatternsProcessor atualiza padrões
 */

import { Injectable, Logger, NotFoundException } from '@nestjs/common';
import { PrismaService } from '../prisma/prisma.service';
import { CacheService } from '../cache/cache.service';
import { EventBusService } from '../shared/events/event-bus.service';
import { DOMAIN_EVENTS } from '../shared/events/domain-events';
import { scrapeProduct } from './scrapers/dispatcher';
import { detectMarketplace, detectStoreName } from './scrapers/registry';
import { ScraperHealthService } from './scraper-health.service';
import { SourceAdapterRegistry } from './sources/source-adapter.registry';
import { HtmlSnapshotService } from './sources/html-snapshot.service';
import { ScraperCircuitBreakerService } from './sources/circuit-breaker.service';
import { SourceScrapeResult } from './sources/source-adapter.interface';
import { ProxyPoolService } from './sources/proxy-pool.service';
import { ScraperDomainMetricsService } from './sources/domain-metrics.service';
import { classifyScrapeError } from './sources/scrape-error';
import { ScrapedProduct } from './scrapers/base.scraper';

@Injectable()
export class CrawlerService {
  private readonly logger = new Logger(CrawlerService.name);

  constructor(
    private prisma:    PrismaService,
    private cache:     CacheService,
    private eventBus:  EventBusService,
    private health:    ScraperHealthService,
    private sources:   SourceAdapterRegistry,
    private snapshots: HtmlSnapshotService,
    private circuit:   ScraperCircuitBreakerService,
    private proxies:   ProxyPoolService,
    private metrics:   ScraperDomainMetricsService,
  ) {}

  // ── Scraping direto (sem persistência) ───────────────────────────────────

  async crawlUrl(url: string) {
    await this.cache.acquireRateLimit(url);
    const entry = detectMarketplace(url);

    if (entry && (await this.health.isDisabled(entry.name))) {
      throw new Error(`Scraper "${entry.name}" desativado (health score baixo).`);
    }

    const t0 = Date.now();
    const result = await this.scrapeWithAdapter({
      url,
      marketplace: entry?.name ?? 'unknown',
      attempt: 1,
      priority: 'manual',
    });
    const latencyMs = Date.now() - t0;

    await this.health.record(
      entry?.name ?? 'unknown',
      result.success,
      latencyMs,
      result.error ?? undefined,
    );

    if (!result.success) throw new Error(result.error ?? 'Scraping falhou');
    return { ...result, latencyMs };
  }

  // ── Sincronização de oferta ───────────────────────────────────────────────

  async syncOffer(
    offerId: string,
    options: { attempt?: number; triggeredBy?: 'scheduler' | 'manual' | 'alert' } = {},
  ) {
    const offer = await this.prisma.offer.findUnique({
      where: { id: offerId, deletedAt: null },
      include: {
        product: true,
        marketplace: { select: { name: true } },
      },
    });
    if (!offer) throw new NotFoundException(`Oferta não encontrada: ${offerId}`);

    const entry = detectMarketplace(offer.productUrl);
    const storeName = entry?.name ?? 'unknown';

    // 1. Cache determinístico por store:externalId  (P4)
    const cacheKey = CacheService.productKey(storeName, offer.externalId);
    const cached = await this.cache.getByKey(cacheKey);
    if (cached !== null) {
      this.logger.debug(`Cache hit [${cacheKey}]: R$ ${cached}`);
      return { success: true, cached: true, price: cached, priceChanged: false };
    }

    // 2. Rate limit
    const allowed = await this.cache.acquireRateLimit(offer.productUrl);
    if (!allowed) {
      this.logger.warn(`Rate limit atingido para ${offer.productUrl}`);
      return { success: false, error: 'rate_limit' };
    }

    // 3. Health check
    if (entry && (await this.health.isDisabled(storeName))) {
      this.logger.warn(`[health] Pulando oferta ${offerId} — scraper "${storeName}" desativado.`);
      return { success: false, error: 'scraper_disabled', store: storeName };
    }

    // 4. Scraping + latência  (P1)
    const t0 = Date.now();
    const result = await this.scrapeWithAdapter({
      url: offer.productUrl,
      marketplace: storeName,
      offerId,
      externalId: offer.externalId,
      attempt: options.attempt ?? 1,
      priority: options.triggeredBy ?? 'scheduler',
    });
    const latencyMs = Date.now() - t0;

    // 5. Registra health com errorType tipado  (P2)
    await this.health.record(storeName, result.success, latencyMs, result.error ?? undefined);

    if (!result.success || result.price === null) {
      this.logger.warn(
        `Scraping falhou [${storeName}] oferta ${offerId}: ${result.error} (${latencyMs}ms)`,
      );
      const snapshotPath = await this.snapshots.saveFailure({
        marketplace: storeName,
        offerId,
        url: offer.productUrl,
        html: (result as SourceScrapeResult).htmlSnapshot,
        error: result.error,
        errorType: (result as SourceScrapeResult).errorType,
        statusCode: (result as SourceScrapeResult).statusCode,
        finalUrl: (result as SourceScrapeResult).finalUrl,
        proxyLabel: (result as SourceScrapeResult).proxy?.label,
        proxyUrl: (result as SourceScrapeResult).proxy?.url,
        responseHeaders: (result as SourceScrapeResult).responseHeaders,
        screenshotPath: (result as SourceScrapeResult).screenshotPath,
      });
      await this.logScrapeRun({
        marketplace: storeName,
        offerId,
        url: offer.productUrl,
        result: result as SourceScrapeResult,
        latencyMs,
        attempt: options.attempt ?? 1,
        priority: options.triggeredBy ?? 'scheduler',
        snapshotPath,
      });
      await this.prisma.offer.update({
        where: { id: offerId },
        data: {
          scrapingStatus: result.error ?? 'failure',
          lastScrapedAt: new Date(),
          lastCheckedAt: new Date(),
        },
      });
      return { success: false, error: result.error, latencyMs, snapshotPath };
    }

    const newPrice       = result.price;
    const previousPrice  = Number(offer.price);
    const priceChanged   = Math.abs(newPrice - previousPrice) >= 0.01;
    const wasAvailable   = offer.availability;
    const nowAvailable   = result.availability;

    // 6. Atualiza oferta
    const unitPrice = this.pricePerUnit(newPrice, offer.product.quantity);
    await this.prisma.offer.update({
      where: { id: offerId },
      data: {
        price: newPrice,
        currentPrice: newPrice,
        originalPrice: result.originalPrice ?? undefined,
        pricePerUnit: unitPrice,
        availability: nowAvailable,
        scrapingStatus: 'success',
        lastCheckedAt: new Date(),
        lastScrapedAt: new Date(),
        lastValidPrice: newPrice,
        lastValidScrapedAt: new Date(),
      },
    });

    // 7. PriceHistory se preço mudou
    if (priceChanged) {
      await this.prisma.priceHistory.create({
        data: { price: newPrice, offer: { connect: { id: offerId } } },
      });
    }

    // 8. Emite eventos de domínio — listeners reagem de forma assíncrona
    if (priceChanged || wasAvailable !== nowAvailable) {
      this.eventBus.emit(DOMAIN_EVENTS.OFFER_PRICE_UPDATED, {
        offerId,
        productId:    offer.product.id,
        marketplace:  offer.marketplace.name,
        oldPrice:     previousPrice,
        newPrice,
        availability: nowAvailable,
      });
    }

    if (!wasAvailable && nowAvailable) {
      this.eventBus.emit(DOMAIN_EVENTS.OFFER_BACK_IN_STOCK, {
        offerId,
        productId:    offer.product.id,
        marketplace:  offer.marketplace.name,
        oldPrice:     null,
        newPrice,
        availability: true,
      });
    }

    if (wasAvailable && !nowAvailable) {
      this.eventBus.emit(DOMAIN_EVENTS.OFFER_OUT_OF_STOCK, {
        offerId,
        productId:    offer.product.id,
        marketplace:  offer.marketplace.name,
        oldPrice:     previousPrice,
        newPrice,
        availability: false,
      });
    }

    // 9. Atualiza cache determinístico — TTL = 4h
    await this.cache.setByKey(cacheKey, newPrice, 4 * 3600);
    await this.logScrapeRun({
      marketplace: storeName,
      offerId,
      url: offer.productUrl,
      result: result as SourceScrapeResult,
      latencyMs,
      attempt: options.attempt ?? 1,
      priority: options.triggeredBy ?? 'scheduler',
    });

    return {
      success: true,
      cached: false,
      priceChanged,
      previousPrice,
      currentPrice: newPrice,
      store: storeName,
      availability: result.availability,
      latencyMs,
    };
  }

  // ── Lookup para fila ─────────────────────────────────────────────────────

  async getOfferForQueue(offerId: string): Promise<{ id: string; marketplace: string; productUrl: string } | null> {
    const offer = await this.prisma.offer.findUnique({
      where: { id: offerId, deletedAt: null },
      include: { marketplace: { select: { name: true } } },
    });
    if (!offer) return null;
    return {
      id:          offer.id,
      marketplace: detectStoreName(offer.productUrl) ?? offer.marketplace.name,
      productUrl:  offer.productUrl,
    };
  }

  // ── Listagem para scheduler ───────────────────────────────────────────────

  async getActiveOffers() {
    const disabledStores = await this.health.getDisabled();

    const disabledIds = disabledStores.length
      ? (await this.prisma.marketplace.findMany({
          where: { OR: disabledStores.map((n) => ({ name: { contains: n } })) },
          select: { id: true },
        })).map((m) => m.id)
      : [];

    const base = {
      deletedAt: null,
      product: { deletedAt: null },
      ...(disabledIds.length ? { marketplaceId: { notIn: disabledIds } } : {}),
    };

    const [withAlerts, withoutAlerts] = await Promise.all([
      this.prisma.offer.findMany({
        where: { ...base, product: { deletedAt: null, alerts: { some: { active: true } } } },
        include: { marketplace: { select: { name: true } } },
        orderBy: { lastCheckedAt: 'asc' },
      }),
      this.prisma.offer.findMany({
        where: { ...base, product: { deletedAt: null, alerts: { none: { active: true } } } },
        include: { marketplace: { select: { name: true } } },
        orderBy: { lastCheckedAt: 'asc' },
      }),
    ]);

    // Marca ofertas com alertas ativos para o scheduler detectar prioridade
    const tagged = [
      ...withAlerts.map((o) => Object.assign(o, { _hasAlerts: true })),
      ...withoutAlerts.map((o) => Object.assign(o, { _hasAlerts: false })),
    ];
    return tagged;
  }

  /**
   * Retorna o mapa de health por marketplace — usado pelo scheduler adaptativo.
   */
  async getHealthMap(): Promise<Map<string, { successRate: number; disabled: boolean }>> {
    const all = await this.health.getAll();
    return new Map(all.map((h) => [h.marketplace, { successRate: h.successRate, disabled: h.disabled }]));
  }

  private async scrapeWithAdapter(context: {
    url: string;
    marketplace: string;
    offerId?: string;
    externalId?: string;
    attempt: number;
    priority: 'manual' | 'alert' | 'scheduler';
  }): Promise<ScrapedProduct | SourceScrapeResult> {
    const adapter = this.sources.find(context.url, context.marketplace);
    if (!adapter) return scrapeProduct(context.url, context.marketplace);

    if (!this.circuit.canRequest(adapter.source)) {
      return {
        success: false,
        price: null,
        name: null,
        imageUrl: null,
        originalPrice: null,
        availability: false,
        error: 'circuit_breaker_open',
        errorType: 'CIRCUIT_BREAKER_OPEN',
        store: adapter.source,
        scrapedAt: new Date(),
        discountPercentage: null,
      };
    }

    let proxy = this.proxies.next(adapter.source);
    let result = await adapter.scrape({
      url: context.url,
      marketplace: adapter.source,
      offerId: context.offerId,
      externalId: context.externalId,
      attempt: context.attempt,
      priority: context.priority,
      proxy,
      adaptiveDelay: this.metrics.delayFor(context.url),
    });

    if (!result.success && this.shouldRetryWithProxy(result) && this.proxies.hasAlternative(adapter.source, proxy)) {
      this.proxies.recordFailure(
        adapter.source,
        proxy,
        result.errorType ?? result.error ?? String(result.statusCode ?? 'failure'),
      );
      proxy = this.proxies.next(adapter.source);
      result = await adapter.scrape({
        url: context.url,
        marketplace: adapter.source,
        offerId: context.offerId,
        externalId: context.externalId,
        attempt: context.attempt + 1,
        priority: context.priority,
        proxy,
        adaptiveDelay: this.metrics.delayFor(context.url),
      });
    }

    await this.metrics.record({
      url: context.url,
      success: result.success,
      statusCode: result.statusCode,
      error: result.errorType ?? result.error,
    });

    if (result.success) {
      this.circuit.recordSuccess(adapter.source);
      this.proxies.recordSuccess(adapter.source, proxy);
    } else {
      this.circuit.recordFailure(adapter.source);
      this.proxies.recordFailure(
        adapter.source,
        proxy,
        result.errorType ?? result.error ?? String(result.statusCode ?? 'failure'),
      );
    }

    return result;
  }

  private shouldRetryWithProxy(result: SourceScrapeResult): boolean {
    if ([401, 403, 429, 502, 503].includes(result.statusCode ?? 0)) return true;
    const type = result.errorType ?? classifyScrapeError(result);
    if (['BLOCKED', 'CAPTCHA', 'RATE_LIMIT', 'NETWORK_ERROR', 'PROXY_ERROR', 'TIMEOUT'].includes(type)) return true;
    return /captcha|bloqueio|blocked|proxy|timeout|socket|econn/i.test(result.error ?? '');
  }

  private pricePerUnit(price: number, quantity: number | null | undefined): number | null {
    if (!quantity || quantity <= 0) return null;
    return Math.round((price / quantity) * 10_000) / 10_000;
  }

  private async logScrapeRun(input: {
    marketplace: string;
    offerId?: string;
    url: string;
    result: SourceScrapeResult;
    latencyMs: number;
    attempt: number;
    priority: 'manual' | 'alert' | 'scheduler';
    snapshotPath?: string | null;
  }): Promise<void> {
    await this.prisma.scraperRunLog.create({
      data: {
        marketplace: input.marketplace,
        offerId: input.offerId,
        url: input.url,
        finalUrl: input.result.finalUrl,
        success: input.result.success,
        statusCode: input.result.statusCode,
        errorType: input.result.errorType ?? (input.result.success ? null : classifyScrapeError(input.result)),
        error: input.result.error,
        latencyMs: input.latencyMs,
        attempt: input.attempt,
        priority: input.priority,
        proxyLabel: input.result.proxy?.label,
        snapshotPath: input.snapshotPath,
        screenshotPath: input.result.screenshotPath,
      },
    }).catch((err) => {
      this.logger.debug(`[scrape-log] falha ao persistir log: ${err.message}`);
    });
  }
}
