/**
 * scraper-health.service.ts
 *
 * Rastreia saúde, latência e tipos de erro por marketplace.
 *
 * Por scraping:
 *   record(marketplace, success, latencyMs, errorType?)
 *     → upsert ScraperHealth  (agregado: successRate, avgLatency, errorBreakdown)
 *     → insert ScraperMetric  (timeline: 1 linha por tentativa)
 *
 * Auto-desativa quando successRate < 20% com >= 10 amostras.
 * Auto-reabilita após 24h de quarentena ou ao primeiro sucesso.
 */

import { Injectable, Logger, Optional } from '@nestjs/common';
import { PrismaService } from '../prisma/prisma.service';
import { IncidentDetector } from '../ai-ops/incidents/incident.detector';
import {
  ScraperErrorType,
  classifyError,
  deserializeBreakdown,
  serializeBreakdown,
} from './scraper-error';

const DISABLE_THRESHOLD  = 20;   // % — desativa abaixo disso
const MIN_SAMPLES        = 10;   // amostras mínimas antes de desativar
const AUTO_REENABLE_MS   = 24 * 60 * 60 * 1000;
const METRIC_RETENTION_DAYS = 30;

export interface HealthStats {
  marketplace: string;
  successCount: number;
  failureCount: number;
  successRate: number;
  avgLatencyMs: number | null;
  lastLatencyMs: number | null;
  errorBreakdown: Record<ScraperErrorType, number>;
  lastSuccessAt: Date | null;
  lastFailureAt: Date | null;
  lastError: string | null;
  lastErrorType: string | null;
  disabled: boolean;
}

@Injectable()
export class ScraperHealthService {
  private readonly logger = new Logger(ScraperHealthService.name);

  constructor(
    private prisma: PrismaService,
    @Optional() private incidentDetector?: IncidentDetector,
  ) {}

  // ── Registro ──────────────────────────────────────────────────────────────

  async record(
    marketplace: string,
    success: boolean,
    latencyMs: number,
    error?: string,
  ): Promise<void> {
    const now = new Date();
    const errorType = success ? undefined : classifyError(error);

    // 1. Persiste métrica individual (timeline)
    await this.prisma.scraperMetric.create({
      data: {
        marketplace,
        latencyMs,
        success,
        errorType: errorType ?? null,
      },
    });

    // 2. Lê agregado atual
    const current = await this.prisma.scraperHealth.findUnique({
      where: { marketplace },
    });

    const successCount = (current?.successCount ?? 0) + (success ? 1 : 0);
    const failureCount = (current?.failureCount ?? 0) + (success ? 0 : 1);
    const total = successCount + failureCount;
    const successRate = Math.round((successCount / total) * 1000) / 10;

    // Média móvel de latência (EMA com alfa=0.2 para suavizar picos)
    const prevAvg = current?.avgLatencyMs ?? latencyMs;
    const avgLatencyMs = Math.round(prevAvg * 0.8 + latencyMs * 0.2);

    // Atualiza breakdown de erros
    const breakdown = deserializeBreakdown(current?.errorBreakdown ?? null);
    if (errorType) breakdown[errorType] = (breakdown[errorType] ?? 0) + 1;

    // Decisão de desativar
    const shouldDisable =
      !success && successRate < DISABLE_THRESHOLD && total >= MIN_SAMPLES;
    const disabled = success ? false : (current?.disabled ?? false) || shouldDisable;

    if (shouldDisable && !current?.disabled) {
      this.logger.warn(
        `[health] "${marketplace}" desativado — taxa de sucesso: ${successRate}%`,
      );
    }
    if (success && current?.disabled) {
      this.logger.log(`[health] "${marketplace}" reabilitado apos sucesso.`);
    }

    // 3. Upsert agregado
    await this.prisma.scraperHealth.upsert({
      where: { marketplace },
      update: {
        successCount,
        failureCount,
        successRate,
        avgLatencyMs,
        lastLatencyMs: latencyMs,
        errorBreakdown: serializeBreakdown(breakdown),
        lastSuccessAt: success ? now : undefined,
        lastFailureAt: success ? undefined : now,
        lastError: success ? null : (error ?? null),
        lastErrorType: success ? null : (errorType ?? null),
        disabled,
      },
      create: {
        marketplace,
        successCount,
        failureCount,
        successRate,
        avgLatencyMs,
        lastLatencyMs: latencyMs,
        errorBreakdown: serializeBreakdown(breakdown),
        lastSuccessAt: success ? now : null,
        lastFailureAt: success ? null : now,
        lastError: success ? null : (error ?? null),
        lastErrorType: success ? null : (errorType ?? null),
        disabled,
      },
    });

    // 4. AI Ops — avalia se há incidente após cada registro (fire-and-forget)
    //    @Optional() garante que funciona mesmo se AiOpsModule não estiver disponível
    this.incidentDetector?.evaluate(marketplace).catch((err) => {
      this.logger.debug(`[health] IncidentDetector silenced error: ${err?.message}`);
    });
  }

  // ── Estado ────────────────────────────────────────────────────────────────

  async isDisabled(marketplace: string): Promise<boolean> {
    const h = await this.prisma.scraperHealth.findUnique({ where: { marketplace } });
    if (!h?.disabled) return false;

    if (h.lastFailureAt && Date.now() - h.lastFailureAt.getTime() >= AUTO_REENABLE_MS) {
      await this.prisma.scraperHealth.update({
        where: { marketplace },
        data: { disabled: false },
      });
      this.logger.log(`[health] "${marketplace}" reabilitado por timeout de quarentena.`);
      return false;
    }

    return true;
  }

  async getDisabled(): Promise<string[]> {
    const rows = await this.prisma.scraperHealth.findMany({
      where: { disabled: true },
      select: { marketplace: true },
    });
    return rows.map((r) => r.marketplace);
  }

  // ── Consultas — P1 métricas ───────────────────────────────────────────────

  async getAll(): Promise<HealthStats[]> {
    const rows = await this.prisma.scraperHealth.findMany({
      orderBy: { successRate: 'asc' },
    });
    return rows.map(this.toStats);
  }

  async getOne(marketplace: string): Promise<HealthStats | null> {
    const row = await this.prisma.scraperHealth.findUnique({ where: { marketplace } });
    return row ? this.toStats(row) : null;
  }

  /**
   * Ranking de marketplaces: do mais saudável ao mais problemático.
   * Inclui successRate, avgLatency e contagem de erros por tipo.
   */
  async getRanking() {
    const all = await this.getAll();
    return all
      .map((h) => ({
        marketplace: h.marketplace,
        successRate: h.successRate,
        avgLatencyMs: h.avgLatencyMs,
        totalRequests: h.successCount + h.failureCount,
        topError: this.topError(h.errorBreakdown),
        disabled: h.disabled,
      }))
      .sort((a, b) => b.successRate - a.successRate);
  }

  /**
   * Timeline de uma métrica para um marketplace.
   * Retorna pontos agrupados por hora para reduzir volume.
   */
  async getTimeline(marketplace: string, days = 7) {
    const since = new Date();
    since.setDate(since.getDate() - days);

    const rows = await this.prisma.scraperMetric.findMany({
      where: { marketplace, capturedAt: { gte: since } },
      orderBy: { capturedAt: 'asc' },
      select: { capturedAt: true, latencyMs: true, success: true, errorType: true },
    });

    // Agrupa por hora
    const byHour = new Map<
      string,
      { hour: string; successes: number; failures: number; totalLatency: number; count: number; errors: Record<string, number> }
    >();

    for (const row of rows) {
      const hour = row.capturedAt.toISOString().slice(0, 13); // YYYY-MM-DDTHH
      const existing = byHour.get(hour) ?? {
        hour,
        successes: 0,
        failures: 0,
        totalLatency: 0,
        count: 0,
        errors: {},
      };
      if (row.success) existing.successes++;
      else {
        existing.failures++;
        if (row.errorType) existing.errors[row.errorType] = (existing.errors[row.errorType] ?? 0) + 1;
      }
      existing.totalLatency += row.latencyMs;
      existing.count++;
      byHour.set(hour, existing);
    }

    return Array.from(byHour.values()).map((h) => ({
      hour: h.hour,
      successes: h.successes,
      failures: h.failures,
      successRate: h.count > 0 ? Math.round((h.successes / h.count) * 100) : 0,
      avgLatencyMs: h.count > 0 ? Math.round(h.totalLatency / h.count) : 0,
      errors: h.errors,
    }));
  }

  /**
   * Breakdown de reasons de falha para um marketplace.
   */
  async getFailureReasons(marketplace: string, days = 30) {
    const since = new Date();
    since.setDate(since.getDate() - days);

    const rows = await this.prisma.scraperMetric.findMany({
      where: { marketplace, success: false, capturedAt: { gte: since } },
      select: { errorType: true },
    });

    const counts: Record<string, number> = {};
    for (const row of rows) {
      const key = row.errorType ?? 'UNKNOWN';
      counts[key] = (counts[key] ?? 0) + 1;
    }

    return Object.entries(counts)
      .map(([type, count]) => ({ type, count }))
      .sort((a, b) => b.count - a.count);
  }

  // ── Limpeza ───────────────────────────────────────────────────────────────

  async pruneOldMetrics(): Promise<number> {
    const cutoff = new Date();
    cutoff.setDate(cutoff.getDate() - METRIC_RETENTION_DAYS);

    const { count } = await this.prisma.scraperMetric.deleteMany({
      where: { capturedAt: { lt: cutoff } },
    });

    if (count > 0) this.logger.log(`[metrics] Removidas ${count} metricas antigas.`);
    return count;
  }

  // ── Helpers ───────────────────────────────────────────────────────────────

  private toStats(row: {
    marketplace: string;
    successCount: number;
    failureCount: number;
    successRate: number;
    avgLatencyMs: number | null;
    lastLatencyMs: number | null;
    errorBreakdown: string | null;
    lastSuccessAt: Date | null;
    lastFailureAt: Date | null;
    lastError: string | null;
    lastErrorType: string | null;
    disabled: boolean;
  }): HealthStats {
    return {
      ...row,
      errorBreakdown: deserializeBreakdown(row.errorBreakdown),
    };
  }

  private topError(breakdown: Record<ScraperErrorType, number>): string | null {
    const entries = Object.entries(breakdown).filter(([, v]) => v > 0);
    if (entries.length === 0) return null;
    return entries.sort(([, a], [, b]) => b - a)[0][0];
  }
}
