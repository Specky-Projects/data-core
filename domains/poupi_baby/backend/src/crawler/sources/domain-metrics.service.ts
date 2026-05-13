import { Injectable, OnModuleInit } from '@nestjs/common';
import { PrismaService } from '../../prisma/prisma.service';

type DomainMetric = {
  domain: string;
  total: number;
  success: number;
  blocks: number;
  rateLimits: number;
  failures: number;
  lastStatusCode?: number;
  lastError?: string | null;
  lastSeenAt: number;
};

@Injectable()
export class ScraperDomainMetricsService implements OnModuleInit {
  private readonly metrics = new Map<string, DomainMetric>();

  constructor(private readonly prisma: PrismaService) {}

  async onModuleInit() {
    const rows = await this.prisma.scraperDomainMetric.findMany().catch(() => []);
    for (const row of rows) {
      this.metrics.set(row.domain, {
        domain: row.domain,
        total: row.total,
        success: row.success,
        blocks: row.blocks,
        rateLimits: row.rateLimits,
        failures: row.failures,
        lastStatusCode: row.lastStatusCode ?? undefined,
        lastError: row.lastError,
        lastSeenAt: row.lastSeenAt.getTime(),
      });
    }
  }

  async record(input: {
    url: string;
    success: boolean;
    statusCode?: number;
    error?: string | null;
  }): Promise<void> {
    const domain = this.domainOf(input.url);
    const current = this.metrics.get(domain) ?? {
      domain,
      total: 0,
      success: 0,
      blocks: 0,
      rateLimits: 0,
      failures: 0,
      lastSeenAt: 0,
    };

    current.total += 1;
    current.lastSeenAt = Date.now();
    current.lastStatusCode = input.statusCode;
    current.lastError = input.error;

    if (input.success) current.success += 1;
    else current.failures += 1;

    if (input.statusCode === 429) current.rateLimits += 1;
    if (this.isBlock(input.statusCode, input.error)) current.blocks += 1;

    this.metrics.set(domain, current);
    const delay = this.delayFor(input.url);

    await this.prisma.scraperDomainMetric.upsert({
      where: { domain },
      update: {
        total: current.total,
        success: current.success,
        blocks: current.blocks,
        rateLimits: current.rateLimits,
        failures: current.failures,
        minDelayMs: delay.minMs,
        maxDelayMs: delay.maxMs,
        lastStatusCode: current.lastStatusCode,
        lastError: current.lastError,
        lastSeenAt: new Date(current.lastSeenAt),
      },
      create: {
        domain,
        total: current.total,
        success: current.success,
        blocks: current.blocks,
        rateLimits: current.rateLimits,
        failures: current.failures,
        minDelayMs: delay.minMs,
        maxDelayMs: delay.maxMs,
        lastStatusCode: current.lastStatusCode,
        lastError: current.lastError,
        lastSeenAt: new Date(current.lastSeenAt),
      },
    }).catch(() => undefined);
  }

  delayFor(url: string): { minMs: number; maxMs: number } {
    const metric = this.metrics.get(this.domainOf(url));
    if (!metric || metric.total < 3) return { minMs: 3_000, maxMs: 12_000 };

    const pressure = (metric.blocks + metric.rateLimits * 1.5 + metric.failures * 0.5) / metric.total;
    if (pressure >= 0.6) return { minMs: 20_000, maxMs: 60_000 };
    if (pressure >= 0.3) return { minMs: 10_000, maxMs: 30_000 };
    return { minMs: 5_000, maxMs: 15_000 };
  }

  snapshot(domain?: string) {
    if (domain) return this.metrics.get(domain) ?? null;
    return [...this.metrics.values()].map((metric) => ({
      ...metric,
      lastSeenAt: new Date(metric.lastSeenAt),
      successRate: metric.total ? metric.success / metric.total : 0,
      blockRate: metric.total ? metric.blocks / metric.total : 0,
    }));
  }

  private isBlock(statusCode?: number, error?: string | null): boolean {
    if ([401, 403, 429].includes(statusCode ?? 0)) return true;
    return /captcha|bloqueio|blocked|rate.limit|access.denied|bot/i.test(error ?? '');
  }

  private domainOf(url: string): string {
    try {
      return new URL(url).hostname.replace(/^www\./, '');
    } catch {
      return 'unknown';
    }
  }
}
