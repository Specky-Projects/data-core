import { Injectable, Logger, OnModuleInit } from '@nestjs/common';
import * as crypto from 'node:crypto';
import { PrismaService } from '../../prisma/prisma.service';
import { ProxyConfig } from './source-adapter.interface';

type ProxyState = ProxyConfig & {
  source: string;
  failures: number;
  successes: number;
  banScore: number;
  cooldownUntil: number | null;
  lastUsedAt: number;
};

const BASE_COOLDOWN_MS = 10 * 60_000;
const MAX_BAN_SCORE = 10;

@Injectable()
export class ProxyPoolService implements OnModuleInit {
  private readonly logger = new Logger(ProxyPoolService.name);
  private readonly pool = new Map<string, ProxyState[]>();

  constructor(private readonly prisma: PrismaService) {
    this.loadFromEnv();
  }

  async onModuleInit() {
    const rows: Array<{ source: string; proxyHash: string; failures: number; successes: number; banScore: number; cooldownUntil: Date | null; lastUsedAt: Date | null }> =
      await this.prisma.scraperProxyState.findMany().catch(() => []);
    for (const proxies of this.pool.values()) {
      for (const proxy of proxies) {
        const persisted = rows.find((row) => row.source === proxy.source && row.proxyHash === this.hash(proxy.url));
        if (!persisted) continue;
        proxy.failures = persisted.failures;
        proxy.successes = persisted.successes;
        proxy.banScore = persisted.banScore;
        proxy.cooldownUntil = persisted.cooldownUntil?.getTime() ?? null;
        proxy.lastUsedAt = persisted.lastUsedAt?.getTime() ?? 0;
      }
    }
  }

  next(source: string): ProxyConfig | undefined {
    const candidates = this.candidates(source);
    const now = Date.now();
    const available = candidates
      .filter((proxy) => !proxy.cooldownUntil || proxy.cooldownUntil <= now)
      .sort((a, b) => a.banScore - b.banScore || a.lastUsedAt - b.lastUsedAt);

    const selected = available[0];
    if (!selected) return undefined;

    selected.lastUsedAt = now;
    return { url: selected.url, label: selected.label };
  }

  hasAlternative(source: string, current?: ProxyConfig): boolean {
    const now = Date.now();
    return this.candidates(source).some((proxy) => {
      if (current?.url && proxy.url === current.url) return false;
      return !proxy.cooldownUntil || proxy.cooldownUntil <= now;
    });
  }

  recordSuccess(source: string, proxy?: ProxyConfig): void {
    const state = this.find(source, proxy);
    if (!state) return;

    state.successes += 1;
    state.failures = 0;
    state.banScore = Math.max(0, state.banScore - 1);
    state.cooldownUntil = null;
    this.persist(state).catch(() => undefined);
  }

  recordFailure(source: string, proxy: ProxyConfig | undefined, reason?: string): void {
    const state = this.find(source, proxy);
    if (!state) return;

    state.failures += 1;
    state.banScore = Math.min(MAX_BAN_SCORE, state.banScore + this.weight(reason));
    const cooldown = BASE_COOLDOWN_MS * Math.max(1, state.banScore);
    state.cooldownUntil = Date.now() + cooldown;

    this.logger.warn(
      `[proxy] ${state.label ?? state.url} em cooldown por ${Math.round(cooldown / 1000)}s (${reason ?? 'failure'})`,
    );
    this.persist(state).catch(() => undefined);
  }

  reset(source?: string): number {
    const groups = source ? [this.candidates(source)] : [...this.pool.values()];
    let count = 0;
    for (const proxies of groups) {
      for (const proxy of proxies) {
        proxy.failures = 0;
        proxy.banScore = 0;
        proxy.cooldownUntil = null;
        count++;
        this.persist(proxy).catch(() => undefined);
      }
    }
    return count;
  }

  getSnapshot(source?: string) {
    const entries: Array<[string, ProxyState[]]> = source
      ? [[source, this.candidates(source)]]
      : [...this.pool.entries()];
    return entries.flatMap(([name, proxies]) =>
      proxies.map((proxy) => ({
        source: name,
        label: proxy.label,
        failures: proxy.failures,
        successes: proxy.successes,
        banScore: proxy.banScore,
        cooldownUntil: proxy.cooldownUntil ? new Date(proxy.cooldownUntil) : null,
        lastUsedAt: proxy.lastUsedAt ? new Date(proxy.lastUsedAt) : null,
      })),
    );
  }

  private loadFromEnv() {
    const global = this.parseList(process.env.SCRAPER_PROXIES ?? process.env.SCRAPER_PROXY_URL, 'global');
    if (global.length) this.pool.set('default', global);

    for (const [key, value] of Object.entries(process.env)) {
      const match = key.match(/^SCRAPER_PROX(?:Y|IES)_(.+)$/);
      if (!match || !value) continue;
      this.pool.set(match[1].toLowerCase(), this.parseList(value, match[1].toLowerCase()));
    }
  }

  private parseList(raw: string | undefined, source: string): ProxyState[] {
    if (!raw) return [];

    const urls = raw.trim().startsWith('[')
      ? this.parseJson(raw)
      : raw.split(',').map((item) => item.trim()).filter(Boolean);

    return urls.map((url, index) => ({
      url,
      label: `${source}-${index + 1}`,
      source,
      failures: 0,
      successes: 0,
      banScore: 0,
      cooldownUntil: null,
      lastUsedAt: 0,
    }));
  }

  private parseJson(raw: string): string[] {
    try {
      const parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? parsed.filter((item) => typeof item === 'string') : [];
    } catch {
      return [];
    }
  }

  private candidates(source: string): ProxyState[] {
    return this.pool.get(source.toLowerCase()) ?? this.pool.get('default') ?? [];
  }

  private find(source: string, proxy?: ProxyConfig): ProxyState | undefined {
    if (!proxy?.url) return undefined;
    return this.candidates(source).find((item) => item.url === proxy.url);
  }

  private weight(reason?: string): number {
    if (!reason) return 1;
    if (/captcha|block|403|429|proxy/i.test(reason)) return 3;
    if (/timeout|network|socket|econn/i.test(reason)) return 2;
    return 1;
  }

  private hash(url: string): string {
    return crypto.createHash('sha256').update(url).digest('hex');
  }

  private redacted(url: string): string {
    try {
      const parsed = new URL(url);
      if (parsed.username) parsed.username = '***';
      if (parsed.password) parsed.password = '***';
      return parsed.toString();
    } catch {
      return url.replace(/\/\/[^:@/]+:[^@/]+@/, '//***:***@');
    }
  }

  private async persist(proxy: ProxyState): Promise<void> {
    await this.prisma.scraperProxyState.upsert({
      where: {
        source_proxyHash: {
          source: proxy.source,
          proxyHash: this.hash(proxy.url),
        },
      },
      update: {
        label: proxy.label ?? this.redacted(proxy.url),
        successes: proxy.successes,
        failures: proxy.failures,
        banScore: proxy.banScore,
        cooldownUntil: proxy.cooldownUntil ? new Date(proxy.cooldownUntil) : null,
        lastUsedAt: proxy.lastUsedAt ? new Date(proxy.lastUsedAt) : null,
      },
      create: {
        source: proxy.source,
        proxyHash: this.hash(proxy.url),
        label: proxy.label ?? this.redacted(proxy.url),
        successes: proxy.successes,
        failures: proxy.failures,
        banScore: proxy.banScore,
        cooldownUntil: proxy.cooldownUntil ? new Date(proxy.cooldownUntil) : null,
        lastUsedAt: proxy.lastUsedAt ? new Date(proxy.lastUsedAt) : null,
      },
    });
  }
}
