import { Injectable } from '@nestjs/common';
import { CacheService } from '../cache/cache.service';
import { ScraperQueueService } from '../crawler/queue/scraper-queue.service';
import { PrismaService } from '../prisma/prisma.service';

type CheckStatus = 'ok' | 'degraded' | 'down';

@Injectable()
export class HealthService {
  constructor(
    private readonly prisma: PrismaService,
    private readonly cache: CacheService,
    private readonly scraperQueue: ScraperQueueService,
  ) {}

  async getHealth() {
    const [database, redis, queue] = await Promise.all([
      this.databaseCheck(),
      this.redisCheck(),
      this.queueCheck(),
    ]);

    const checks = { database, redis, queue };
    const status: CheckStatus = database.status === 'down'
      ? 'down'
      : Object.values(checks).some((check) => check.status !== 'ok')
        ? 'degraded'
        : 'ok';

    return {
      status,
      checks,
      timestamp: new Date().toISOString(),
    };
  }

  private async databaseCheck() {
    const startedAt = Date.now();
    try {
      await this.prisma.$queryRaw`SELECT 1`;
      return { status: 'ok' as const, latencyMs: Date.now() - startedAt };
    } catch (error) {
      return {
        status: 'down' as const,
        latencyMs: Date.now() - startedAt,
        error: (error as Error).message,
      };
    }
  }

  private async redisCheck() {
    try {
      const info = await this.cache.getInfo();
      return {
        status: info.available ? 'ok' as const : 'degraded' as const,
        ...info,
      };
    } catch (error) {
      return {
        status: 'degraded' as const,
        available: false,
        error: (error as Error).message,
      };
    }
  }

  private async queueCheck() {
    try {
      const stats = await this.scraperQueue.getStats();
      return { status: 'ok' as const, ...stats };
    } catch (error) {
      return {
        status: 'degraded' as const,
        error: (error as Error).message,
      };
    }
  }
}
