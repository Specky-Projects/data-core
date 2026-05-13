import { Inject, Injectable, Logger } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import type { IAiProvider } from '../providers/ai-provider.interface';
import { AI_PROVIDER_TOKEN } from '../providers/ai-provider.interface';
import { IncidentService } from '../incidents/incident.service';
import { EventBusService } from '../../shared/events/event-bus.service';
import { DOMAIN_EVENTS } from '../../shared/events/domain-events';
import { buildScraperIncidentPrompt, ScraperIncidentInput } from '../prompts/scraper-incident.prompt';

/**
 * IncidentAnalyzer — orquestra a análise de incidentes via IA.
 *
 * Fluxo:
 *   1. Recebe dados de contexto (métricas de scraper, fila, etc.)
 *   2. Constrói prompt estruturado
 *   3. Chama provider de IA (Claude / OpenAI / Mock)
 *   4. Persiste resultado como AiIncident
 *   5. Emite evento INCIDENT_DETECTED
 */
@Injectable()
export class IncidentAnalyzer {
  private readonly logger = new Logger(IncidentAnalyzer.name);
  private readonly enabled: boolean;

  constructor(
    @Inject(AI_PROVIDER_TOKEN)
    private readonly ai:       IAiProvider,
    private readonly incidents: IncidentService,
    private readonly eventBus:  EventBusService,
    private readonly config:    ConfigService,
  ) {
    this.enabled = this.config.get<boolean>('features.aiOps') ?? false;
  }

  /**
   * Analisa um incidente de scraper e persiste o resultado.
   * Se AI_OPS desabilitado, cria incidente com diagnóstico básico sem chamar IA.
   */
  async analyzeScraperIncident(data: ScraperIncidentInput): Promise<string> {
    const { context, question } = buildScraperIncidentPrompt(data);

    let result;

    if (this.enabled && this.ai.isAvailable()) {
      try {
        result = await this.ai.analyze({ context, question });
        this.logger.log(
          `[ai-ops] Análise concluída — ${data.marketplace} — ${result.severity} — confiança: ${result.confidence}`,
        );
      } catch (err: any) {
        this.logger.error(`[ai-ops] Falha na IA, usando fallback: ${err.message}`);
        result = this.buildFallbackResult(data);
      }
    } else {
      result = this.buildFallbackResult(data);
      this.logger.debug('[ai-ops] Feature FEATURE_AI_OPS desabilitada — usando diagnóstico básico');
    }

    const incident = await this.incidents.create({
      marketplace:  data.marketplace,
      incidentType: 'scraper_degradation',
      severity:     result.severity,
      inputData:    data as unknown as Record<string, unknown>,
      rootCause:    result.rootCause,
      suggestions:  result.suggestions,
      confidence:   result.confidence,
      aiProvider:   result.provider,
      aiModel:      result.model,
      aiTokensUsed: result.tokensUsed,
    });

    this.eventBus.emit(DOMAIN_EVENTS.INCIDENT_DETECTED, {
      incidentId:   incident.id,
      marketplace:  data.marketplace,
      severity:     result.severity,
      incidentType: 'scraper_degradation',
    });

    return incident.id;
  }

  /** Diagnóstico básico sem IA — usado quando feature flag off ou IA indisponível */
  private buildFallbackResult(data: ScraperIncidentInput) {
    const topError = Object.entries(data.errorTypes).sort(([, a], [, b]) => b - a)[0]?.[0] ?? 'unknown';

    const severity =
      data.successRate < 20 ? 'critical' :
      data.successRate < 40 ? 'high' :
      data.successRate < 60 ? 'medium' : 'low';

    return {
      rootCause:    `Degradação de scraping em ${data.marketplace}. Taxa de sucesso: ${data.successRate}%. Erro mais comum: ${topError}.`,
      suggestions:  [
        'Verificar dashboard de saúde do scraper',
        'Reduzir concorrência temporariamente',
        'Ativar FEATURE_AI_OPS=true para diagnóstico inteligente',
      ],
      severity:     severity as any,
      confidence:   0.5,
      estimatedRecoveryMinutes: 30,
      tokensUsed:   0,
      provider:     'fallback',
      model:        'rule-based',
    };
  }
}
