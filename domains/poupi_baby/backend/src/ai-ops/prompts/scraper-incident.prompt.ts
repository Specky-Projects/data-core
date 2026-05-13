/**
 * Prompt de diagnóstico de incidente de scraper.
 * Estruturado para maximizar precisão da IA com contexto mínimo de tokens.
 */
export interface ScraperIncidentInput {
  marketplace:    string;
  successRate:    number;          // 0–100
  avgLatencyMs:   number;
  errorTypes:     Record<string, number>; // { captcha: 5, rate_limit: 3 }
  lastErrors:     string[];
  workerCount:    number;
  concurrency:    number;
  windowMinutes:  number;
  totalSamples:   number;
}

export function buildScraperIncidentPrompt(data: ScraperIncidentInput): {
  context: string;
  question: string;
} {
  const errorSummary = Object.entries(data.errorTypes)
    .sort(([, a], [, b]) => b - a)
    .map(([type, count]) => `${type}: ${count}`)
    .join(', ');

  const context = `
INCIDENTE DE SCRAPING — DADOS COLETADOS

Marketplace:         ${data.marketplace}
Janela de análise:   últimos ${data.windowMinutes} minutos (${data.totalSamples} amostras)
Taxa de sucesso:     ${data.successRate}% (crítico se < 60%)
Latência média:      ${data.avgLatencyMs}ms (crítico se > 8000ms)
Workers ativos:      ${data.workerCount}
Concorrência config: ${data.concurrency} req simultâneas

Tipos de erro (contagem): ${errorSummary || 'nenhum tipo específico'}
Últimas mensagens:   ${data.lastErrors.slice(0, 3).join(' | ') || 'sem mensagem'}

REGRAS DE DIAGNÓSTICO:
- successRate < 20% + erros captcha/403 → bloqueio anti-bot ativo (critical)
- successRate < 40% + rate_limit/429 → throttling agressivo (high)
- successRate < 60% + erros de parse → HTML mudou (high)
- avgLatencyMs > 12000 + poucos erros → instabilidade de rede (medium)
- successRate < 60% sem padrão claro → causa mista (medium)
`.trim();

  const question = 'Qual é a causa raiz deste incidente e quais ações concretas devem ser tomadas imediatamente?';

  return { context, question };
}
