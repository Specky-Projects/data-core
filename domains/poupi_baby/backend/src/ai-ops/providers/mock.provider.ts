import { Injectable } from '@nestjs/common';
import { IAiProvider, AiAnalysisInput, AiAnalysisOutput } from './ai-provider.interface';

/**
 * Provider mock — usado em desenvolvimento e testes.
 * Retorna diagnósticos determinísticos baseados em palavras-chave no contexto.
 * Zero custo, zero latência de rede.
 */
@Injectable()
export class MockAiProvider implements IAiProvider {
  readonly name  = 'mock';
  readonly model = 'mock-v1';

  isAvailable(): boolean { return true; }

  async analyze(input: AiAnalysisInput): Promise<AiAnalysisOutput> {
    const ctx = (input.context + ' ' + input.question).toLowerCase();

    // Diagnóstico determinístico por palavras-chave
    if (ctx.includes('captcha') || ctx.includes('403')) {
      return this.build({
        rootCause:   'Bloqueio anti-bot detectado — CAPTCHA ou 403 Forbidden.',
        suggestions: [
          'Reduzir concorrência para 1 requisição simultânea',
          'Aumentar delay entre requisições para 5–10 segundos',
          'Rotacionar User-Agent e headers',
          'Aguardar 30 minutos antes de reiniciar',
          'Verificar se IP foi banido permanentemente',
        ],
        severity:    'high',
        confidence:  0.88,
        recovery:    45,
      });
    }

    if (ctx.includes('rate_limit') || ctx.includes('429') || ctx.includes('too many')) {
      return this.build({
        rootCause:   'Rate limiting ativo — marketplace detectou volume excessivo.',
        suggestions: [
          'Reduzir WORKER_CONCURRENCY de forma imediata',
          'Implementar backoff exponencial de 60 segundos',
          'Distribuir scraping em janelas horárias',
          'Usar delays aleatórios entre 3–8 segundos',
        ],
        severity:   'medium',
        confidence: 0.92,
        recovery:   20,
      });
    }

    if (ctx.includes('timeout') || ctx.includes('latência') || ctx.includes('latency')) {
      return this.build({
        rootCause:   'Latência elevada — possível instabilidade do marketplace ou da rede.',
        suggestions: [
          'Aumentar timeout de 8s para 15s temporariamente',
          'Verificar conectividade com o marketplace',
          'Reduzir concorrência para aliviar pressão',
          'Aguardar 10 minutos e reavaliar',
        ],
        severity:   'medium',
        confidence: 0.75,
        recovery:   15,
      });
    }

    if (ctx.includes('parse') || ctx.includes('html') || ctx.includes('estrutura')) {
      return this.build({
        rootCause:   'Falha de parsing — marketplace alterou a estrutura do HTML.',
        suggestions: [
          'Atualizar seletores CSS/XPath do scraper',
          'Verificar se URL do produto mudou',
          'Inspecionar o HTML retornado manualmente',
          'Desabilitar scraper temporariamente até atualização',
        ],
        severity:   'high',
        confidence: 0.80,
        recovery:   120,
      });
    }

    // Default genérico
    return this.build({
      rootCause:   'Degradação de scraping detectada — causa específica requer investigação manual.',
      suggestions: [
        'Verificar logs detalhados dos últimos 30 minutos',
        'Reduzir concorrência pela metade temporariamente',
        'Monitorar taxa de sucesso por 15 minutos',
      ],
      severity:   'medium',
      confidence: 0.50,
      recovery:   30,
    });
  }

  private build(data: {
    rootCause:   string;
    suggestions: string[];
    severity:    AiAnalysisOutput['severity'];
    confidence:  number;
    recovery?:   number;
  }): AiAnalysisOutput {
    return {
      rootCause:    data.rootCause,
      suggestions:  data.suggestions,
      severity:     data.severity,
      confidence:   data.confidence,
      estimatedRecoveryMinutes: data.recovery,
      tokensUsed:   0,
      provider:     this.name,
      model:        this.model,
    };
  }
}
