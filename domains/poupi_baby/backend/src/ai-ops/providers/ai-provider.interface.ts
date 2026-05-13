/**
 * Contrato de todos os providers de IA do AI Ops.
 * Implementações: MockProvider, ClaudeProvider, OpenAIProvider.
 *
 * Estratégia de seleção: injetada via AI_PROVIDER env.
 * Fallback automático para mock se provider configurado não estiver disponível.
 */

export interface AiAnalysisInput {
  /** Contexto estruturado (dados do incidente, métricas, etc.) */
  context:   string;
  /** Pergunta específica a ser respondida */
  question:  string;
  maxTokens?: number;
}

export interface AiAnalysisOutput {
  rootCause:    string;
  suggestions:  string[];
  /** Nível de confiança da análise: 0.0 – 1.0 */
  confidence:   number;
  severity:     'low' | 'medium' | 'high' | 'critical';
  /** Estimativa de tempo para recuperação (minutos) */
  estimatedRecoveryMinutes?: number;
  tokensUsed:   number;
  provider:     string;
  model:        string;
}

export interface IAiProvider {
  analyze(input: AiAnalysisInput): Promise<AiAnalysisOutput>;
  isAvailable(): boolean;
  readonly name: string;
  readonly model: string;
}

export const AI_PROVIDER_TOKEN = 'AI_PROVIDER';
