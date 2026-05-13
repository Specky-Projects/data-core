import { Injectable, Logger } from '@nestjs/common';
import { PrismaService } from '../../prisma/prisma.service';
import { IncidentAnalyzer } from '../analyzers/incident.analyzer';
import { IncidentService } from './incident.service';

/**
 * IncidentDetector — observa métricas de scraper e dispara análise de IA
 * quando thresholds de degradação são atingidos.
 *
 * Chamado pelo ScraperHealthService após cada tentativa de scraping.
 * Leve e síncrono — a análise de IA é feita de forma assíncrona (fire-and-forget).
 */

interface DetectionThresholds {
  successRateMin: number;    // % mínima de sucesso (0-100)
  latencyMaxMs:   number;    // latência máxima em ms
  windowMinutes:  number;    // janela de análise
  minSamples:     number;    // amostras mínimas para avaliar
}

const THRESHOLDS: DetectionThresholds = {
  successRateMin: 60,
  latencyMaxMs:   10_000,
  windowMinutes:  10,
  minSamples:     5,
};

@Injectable()
export class IncidentDetector {
  private readonly logger = new Logger(IncidentDetector.name);

  constructor(
    private readonly prisma:    PrismaService,
    private readonly analyzer:  IncidentAnalyzer,
    private readonly incidents: IncidentService,
  ) {}

  /**
   * Avalia se um marketplace entrou em estado de incidente.
   * Deve ser chamado após cada registro de saúde (ScraperHealthService.record).
   *
   * @param marketplace nome do marketplace ('amazon', 'mercadolivre', etc.)
   * @param workerCount número de workers ativos
   * @param concurrency concorrência configurada
   */
  async evaluate(
    marketplace:  string,
    workerCount:  number = 1,
    concurrency:  number = 5,
  ): Promise<void> {
    const windowStart = new Date(Date.now() - THRESHOLDS.windowMinutes * 60_000);

    const metrics = await this.prisma.scraperMetric.findMany({
      where: {
        marketplace,
        capturedAt: { gte: windowStart },
      },
      orderBy: { capturedAt: 'desc' },
    });

    if (metrics.length < THRESHOLDS.minSamples) return;

    const total       = metrics.length;
    const successes   = metrics.filter((m) => m.success).length;
    const successRate = Math.round((successes / total) * 100);
    const avgLatency  = Math.round(
      metrics.filter((m) => m.latencyMs > 0)
             .reduce((s, m) => s + m.latencyMs, 0) / Math.max(1, total),
    );

    const degraded =
      successRate < THRESHOLDS.successRateMin ||
      avgLatency  > THRESHOLDS.latencyMaxMs;

    if (!degraded) return;

    // Evita incidente duplicado (cooldown de 30min)
    const alreadyOpen = await this.incidents.findOpenIncident(marketplace);
    if (alreadyOpen) return;

    this.logger.warn(
      `[detector] Incidente detectado em ${marketplace}: ${successRate}% success, ${avgLatency}ms latência`,
    );

    // Agrega tipos de erro
    const errorTypes: Record<string, number> = {};
    metrics.filter((m) => !m.success && m.errorType).forEach((m) => {
      const t = m.errorType!;
      errorTypes[t] = (errorTypes[t] ?? 0) + 1;
    });

    const lastErrors = metrics
      .filter((m) => !m.success)
      .slice(0, 5)
      .map((m) => m.errorType ?? 'unknown');

    // Dispara análise assíncrona — não bloqueia o pipeline de scraping
    this.analyzer
      .analyzeScraperIncident({
        marketplace,
        successRate,
        avgLatencyMs: avgLatency,
        errorTypes,
        lastErrors,
        workerCount,
        concurrency,
        windowMinutes: THRESHOLDS.windowMinutes,
        totalSamples:  total,
      })
      .catch((err) => {
        this.logger.error(`[detector] Falha ao analisar incidente: ${err.message}`);
      });
  }
}
