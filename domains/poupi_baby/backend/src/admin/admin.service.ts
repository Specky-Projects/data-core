import { Injectable, NotFoundException } from '@nestjs/common';
import { PrismaService } from '../prisma/prisma.service';
import { ScraperHealthService } from '../crawler/scraper-health.service';
import { AnalyticsService } from '../analytics/analytics.service';
import { IncidentService } from '../ai-ops/incidents/incident.service';
import { ScraperQueueService } from '../crawler/queue/scraper-queue.service';
import { ProxyPoolService } from '../crawler/sources/proxy-pool.service';
import { ScraperDomainMetricsService } from '../crawler/sources/domain-metrics.service';
import { ScraperCircuitBreakerService } from '../crawler/sources/circuit-breaker.service';
import { AdminListQueryDto } from './dto/admin-query.dto';

function pageOf(query: AdminListQueryDto) {
  const page = Math.max(1, Number(query.page ?? 1));
  const limit = Math.min(100, Math.max(10, Number(query.limit ?? 25)));
  return { page, limit, skip: (page - 1) * limit };
}

function pages(total: number, limit: number) {
  return Math.max(1, Math.ceil(total / limit));
}

@Injectable()
export class AdminService {
  private overviewCache: { expiresAt: number; data: unknown } | null = null;

  constructor(
    private readonly prisma: PrismaService,
    private readonly health: ScraperHealthService,
    private readonly analytics: AnalyticsService,
    private readonly incidents: IncidentService,
    private readonly scraperQueue: ScraperQueueService,
    private readonly proxyPool: ProxyPoolService,
    private readonly domainMetrics: ScraperDomainMetricsService,
    private readonly circuit: ScraperCircuitBreakerService,
  ) {}

  async overview() {
    const now = Date.now();
    if (this.overviewCache && this.overviewCache.expiresAt > now) {
      return this.overviewCache.data;
    }

    const [
      totalUsers,
      totalProducts,
      totalOffers,
      activeAlerts,
      marketplaces,
      scraperHealth,
      queue,
      recentErrors,
      monitoredProducts,
      lowestPrices,
    ] = await Promise.all([
      this.prisma.user.count({ where: { deletedAt: null } }),
      this.prisma.product.count({ where: { deletedAt: null } }),
      this.prisma.offer.count({ where: { deletedAt: null } }),
      this.prisma.alert.count({ where: { active: true } }),
      this.prisma.marketplace.count({ where: { active: true } }),
      this.health.getRanking(),
      this.scraperQueue.getStats(),
      this.recentErrors(8),
      this.monitoredProducts(8),
      this.lowestPrices(8),
    ]);

    const data = {
      metrics: { totalUsers, totalProducts, totalOffers, activeAlerts, marketplaces },
      scraping: { health: scraperHealth, queue },
      recentErrors,
      monitoredProducts,
      lowestPrices,
      generatedAt: new Date().toISOString(),
    };

    this.overviewCache = { data, expiresAt: now + 20_000 };
    return data;
  }

  async products(query: AdminListQueryDto) {
    const { page, limit, skip } = pageOf(query);
    const where = {
      deletedAt: query.status === 'inactive' ? { not: null as any } : null,
      ...(query.q
        ? {
            OR: [
              { title: { contains: query.q, mode: 'insensitive' as const } },
              { slug: { contains: query.q, mode: 'insensitive' as const } },
              { brand: { contains: query.q, mode: 'insensitive' as const } },
              { category: { contains: query.q, mode: 'insensitive' as const } },
            ],
          }
        : {}),
    };

    const [items, total] = await Promise.all([
      this.prisma.product.findMany({
        where,
        include: {
          offers: {
            where: { deletedAt: null },
            include: { marketplace: true },
            orderBy: { price: 'asc' },
          },
          _count: { select: { alerts: true } },
        },
        orderBy: { createdAt: 'desc' },
        skip,
        take: limit,
      }),
      this.prisma.product.count({ where }),
    ]);

    return { items, pagination: { total, page, limit, pages: pages(total, limit) } };
  }

  async productDetail(id: string) {
    const product = await this.prisma.product.findUnique({
      where: { id },
      include: {
        offers: {
          include: {
            marketplace: true,
            priceHistory: { orderBy: { capturedAt: 'desc' }, take: 60 },
          },
        },
        alerts: { where: { active: true }, take: 20 },
      },
    });
    if (!product) throw new NotFoundException('Produto nao encontrado');
    return product;
  }

  async setProductActive(id: string, active: boolean, adminUserId?: string) {
    const product = await this.prisma.product.update({
      where: { id },
      data: { deletedAt: active ? null : new Date() },
      select: { id: true, title: true, deletedAt: true },
    });
    await this.audit(adminUserId, active ? 'admin.product_enabled' : 'admin.product_disabled', { productId: id });
    return product;
  }

  async offers(query: AdminListQueryDto) {
    const { page, limit, skip } = pageOf(query);
    const where = {
      deletedAt: null,
      ...(query.marketplace ? { marketplace: { name: { contains: query.marketplace, mode: 'insensitive' as const } } } : {}),
      ...(query.status === 'out'
        ? { availability: false }
        : query.status === 'in'
          ? { availability: true }
          : {}),
      ...(query.q
        ? {
            OR: [
              { externalId: { contains: query.q, mode: 'insensitive' as const } },
              { product: { title: { contains: query.q, mode: 'insensitive' as const } } },
            ],
          }
        : {}),
    };

    const [items, total] = await Promise.all([
      this.prisma.offer.findMany({
        where,
        include: {
          product: { select: { id: true, title: true, imageUrl: true } },
          marketplace: true,
          priceHistory: { orderBy: { capturedAt: 'desc' }, take: 2 },
        },
        orderBy: { lastCheckedAt: 'asc' },
        skip,
        take: limit,
      }),
      this.prisma.offer.count({ where }),
    ]);

    return { items: items.map((offer) => ({ ...offer, inconsistency: this.offerIssue(offer) })), pagination: { total, page, limit, pages: pages(total, limit) } };
  }

  async marketplaces() {
    const [items, health] = await Promise.all([
      this.prisma.marketplace.findMany({
        include: { _count: { select: { offers: true } } },
        orderBy: { name: 'asc' },
      }),
      this.health.getRanking(),
    ]);
    const healthMap = new Map(health.map((h) => [h.marketplace.toLowerCase(), h]));
    return items.map((item) => ({ ...item, health: healthMap.get(item.name.toLowerCase()) ?? null }));
  }

  async users(query: AdminListQueryDto) {
    const { page, limit, skip } = pageOf(query);
    const where = {
      ...(query.status === 'blocked' ? { deletedAt: { not: null as any } } : { deletedAt: null }),
      ...(query.role ? { role: query.role as any } : {}),
      ...(query.q
        ? {
            OR: [
              { name: { contains: query.q, mode: 'insensitive' as const } },
              { email: { contains: query.q, mode: 'insensitive' as const } },
            ],
          }
        : {}),
    };
    const [items, total] = await Promise.all([
      this.prisma.user.findMany({
        where,
        select: {
          id: true,
          name: true,
          email: true,
          role: true,
          createdAt: true,
          deletedAt: true,
          _count: { select: { alerts: true, subscriptions: true } },
        },
        orderBy: { createdAt: 'desc' },
        skip,
        take: limit,
      }),
      this.prisma.user.count({ where }),
    ]);
    return { items, pagination: { total, page, limit, pages: pages(total, limit) } };
  }

  async updateUserRole(id: string, role: 'free' | 'premium' | 'admin', adminUserId?: string) {
    const user = await this.prisma.user.update({
      where: { id },
      data: { role },
      select: { id: true, email: true, role: true },
    });
    await this.audit(adminUserId, 'admin.user_role_updated', { targetUserId: id, role });
    return user;
  }

  async blockUser(id: string, blocked: boolean, adminUserId?: string) {
    const user = await this.prisma.user.update({
      where: { id },
      data: { deletedAt: blocked ? new Date() : null },
      select: { id: true, email: true, deletedAt: true },
    });
    await this.audit(adminUserId, blocked ? 'admin.user_blocked' : 'admin.user_unblocked', { targetUserId: id });
    return user;
  }

  async alerts(query: AdminListQueryDto) {
    const { page, limit, skip } = pageOf(query);
    const where = {
      ...(query.status === 'inactive' ? { active: false } : query.status === 'active' ? { active: true } : {}),
      ...(query.q
        ? {
            OR: [
              { user: { email: { contains: query.q, mode: 'insensitive' as const } } },
              { product: { title: { contains: query.q, mode: 'insensitive' as const } } },
            ],
          }
        : {}),
    };
    const [items, total] = await Promise.all([
      this.prisma.alert.findMany({
        where,
        include: {
          user: { select: { id: true, email: true, name: true } },
          product: { select: { id: true, title: true } },
        },
        orderBy: { createdAt: 'desc' },
        skip,
        take: limit,
      }),
      this.prisma.alert.count({ where }),
    ]);
    return { items, pagination: { total, page, limit, pages: pages(total, limit) } };
  }

  async scraping() {
    const [queue, failedJobs, health, incidents] = await Promise.all([
      this.scraperQueue.getStats(),
      this.scraperQueue.getFailedJobs(25),
      this.health.getRanking(),
      this.incidents.getRecent(20),
    ]);
    return {
      queue,
      failedJobs,
      health,
      incidents,
      proxies: {
        global: !!process.env.SCRAPER_PROXY_URL,
        poolSize: this.proxyPool.getSnapshot().length,
        pool: this.proxyPool.getSnapshot(),
      },
      domainMetrics: this.domainMetrics.snapshot(),
      runLogs: await this.recentScraperRunLogs(20),
      snapshotsDir: process.env.SCRAPER_SNAPSHOT_DIR ?? 'storage/scraper-failures',
      sessionsDir: process.env.SCRAPER_SESSION_DIR ?? '.scraper-sessions',
    };
  }

  async pauseScraping(adminUserId?: string) {
    await this.scraperQueue.pause();
    await this.audit(adminUserId, 'admin.scraping_paused', {});
    return { paused: true };
  }

  async resumeScraping(adminUserId?: string) {
    await this.scraperQueue.resume();
    await this.audit(adminUserId, 'admin.scraping_resumed', {});
    return { paused: false };
  }

  async resetProxyCooldowns(source: string | undefined, adminUserId?: string) {
    const reset = this.proxyPool.reset(source);
    await this.audit(adminUserId, 'admin.proxy_cooldowns_reset', { source, reset });
    return { reset };
  }

  async openCircuit(source: string, minutes: number, adminUserId?: string) {
    this.circuit.forceOpen(source, minutes);
    await this.audit(adminUserId, 'admin.circuit_opened', { source, minutes });
    return this.circuit.getState(source);
  }

  async closeCircuit(source: string, adminUserId?: string) {
    this.circuit.close(source);
    await this.audit(adminUserId, 'admin.circuit_closed', { source });
    return this.circuit.getState(source);
  }

  async retryFailedJobs(adminUserId?: string) {
    const retried = await this.scraperQueue.retryFailed();
    await this.audit(adminUserId, 'admin.scraper_jobs_retried', { retried });
    return { retried };
  }

  async analyticsOverview(days = 30) {
    const [events, activeUsers, topProducts, funnel, volatileProducts, promotions] = await Promise.all([
      this.analytics.getEventCounts(days),
      this.analytics.getActiveUsers(days),
      this.analytics.getTopProducts(days, 10),
      this.analytics.getConversionFunnel(days),
      this.volatileProducts(10),
      this.recentPromotions(10),
    ]);
    return { days, events, activeUsers, topProducts, funnel, volatileProducts, promotions };
  }

  async logs(query: AdminListQueryDto) {
    const { page, limit, skip } = pageOf(query);
    const where = {
      ...(query.q ? { eventType: { contains: query.q, mode: 'insensitive' as const } } : {}),
    };
    const [items, total] = await Promise.all([
      this.prisma.userEvent.findMany({ where, orderBy: { occurredAt: 'desc' }, skip, take: limit }),
      this.prisma.userEvent.count({ where }),
    ]);
    return { items, pagination: { total, page, limit, pages: pages(total, limit) } };
  }

  async scrapingLogs(query: AdminListQueryDto) {
    const { page, limit, skip } = pageOf(query);
    const where = {
      ...(query.marketplace ? { marketplace: { contains: query.marketplace, mode: 'insensitive' as const } } : {}),
      ...(query.status === 'failed' ? { success: false } : query.status === 'success' ? { success: true } : {}),
      ...(query.q
        ? {
            OR: [
              { url: { contains: query.q, mode: 'insensitive' as const } },
              { errorType: { contains: query.q, mode: 'insensitive' as const } },
              { error: { contains: query.q, mode: 'insensitive' as const } },
            ],
          }
        : {}),
    };
    const [items, total] = await Promise.all([
      this.prisma.scraperRunLog.findMany({ where, orderBy: { createdAt: 'desc' }, skip, take: limit }),
      this.prisma.scraperRunLog.count({ where }),
    ]).catch(() => [[], 0] as const);
    return { items, pagination: { total, page, limit, pages: pages(total, limit) } };
  }

  async settings() {
    const marketplaces = await this.prisma.marketplace.findMany({ orderBy: { name: 'asc' } });
    return {
      scraping: {
        defaultFrequencyHours: Number(process.env.SCRAPER_DEFAULT_FREQUENCY_HOURS ?? 6),
        alertFrequencyHours: Number(process.env.SCRAPER_ALERT_FREQUENCY_HOURS ?? 2),
        browserMode: process.env.SCRAPER_BROWSER_MODE === 'true',
        calibrationMode: process.env.SCRAPER_CALIBRATION_MODE === 'true',
        calibrationMaxPerDomain: Number(process.env.SCRAPER_CALIBRATION_MAX_PER_DOMAIN ?? 5),
        snapshotDir: process.env.SCRAPER_SNAPSHOT_DIR ?? 'storage/scraper-failures',
        sessionDir: process.env.SCRAPER_SESSION_DIR ?? '.scraper-sessions',
      },
      alerts: {
        priceDropPercent: Number(process.env.ALERT_PRICE_DROP_PERCENT ?? 5),
        cooldownHours: Number(process.env.ALERT_COOLDOWN_HOURS ?? 24),
      },
      featureFlags: {
        aiEnabled: process.env.FEATURE_AI === 'true',
        proxiesEnabled: !!(process.env.SCRAPER_PROXIES ?? process.env.SCRAPER_PROXY_URL),
      },
      marketplaces,
    };
  }

  private async monitoredProducts(limit: number) {
    return this.prisma.product.findMany({
      where: { deletedAt: null, alerts: { some: { active: true } } },
      select: { id: true, title: true, imageUrl: true, _count: { select: { alerts: true } } },
      orderBy: { alerts: { _count: 'desc' } },
      take: limit,
    }).catch(() => []);
  }

  private async lowestPrices(limit: number) {
    return this.prisma.offer.findMany({
      where: { deletedAt: null, availability: true },
      include: { product: { select: { title: true } }, marketplace: true },
      orderBy: { price: 'asc' },
      take: limit,
    });
  }

  private async recentErrors(limit: number) {
    return this.prisma.scraperMetric.findMany({
      where: { success: false },
      orderBy: { capturedAt: 'desc' },
      take: limit,
    });
  }

  private async recentScraperRunLogs(limit: number) {
    return this.prisma.scraperRunLog.findMany({
      orderBy: { createdAt: 'desc' },
      take: limit,
    }).catch(() => []);
  }

  private async volatileProducts(limit: number) {
    return this.prisma.marketPattern.findMany({
      where: { patternType: 'volatility' },
      include: { product: { select: { id: true, title: true } } },
      orderBy: { priceVolatility30d: 'desc' },
      take: limit,
    }).catch(() => []);
  }

  private async recentPromotions(limit: number) {
    return this.prisma.priceHistory.findMany({
      include: { offer: { include: { product: true, marketplace: true } } },
      orderBy: { capturedAt: 'desc' },
      take: limit,
    });
  }

  private offerIssue(offer: { price: any; availability: boolean; lastCheckedAt: Date; priceHistory: Array<{ price: any }> }) {
    const issues: string[] = [];
    if (Number(offer.price) <= 0) issues.push('invalid_price');
    if (Date.now() - new Date(offer.lastCheckedAt).getTime() > 48 * 3600_000) issues.push('stale_scrape');
    const last = offer.priceHistory?.[0];
    if (last && Math.abs(Number(last.price) - Number(offer.price)) > 0.01) issues.push('history_mismatch');
    if (!offer.availability) issues.push('out_of_stock');
    return issues;
  }

  private async audit(userId: string | undefined, eventType: string, payload: Record<string, unknown>) {
    if (!userId) return;
    await this.prisma.userEvent.create({
      data: { userId, eventType, payload: JSON.stringify(payload) },
    }).catch(() => undefined);
  }
}
