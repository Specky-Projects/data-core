import { Injectable, Logger } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import axios from 'axios';
import { IAiProvider, AiAnalysisInput, AiAnalysisOutput } from './ai-provider.interface';

/**
 * Provider Claude (Anthropic).
 * Modelo padrão: claude-3-5-haiku-20241022 (rápido e barato para diagnósticos).
 * Fallback para mock se API key não configurada.
 */
@Injectable()
export class ClaudeProvider implements IAiProvider {
  private readonly logger = new Logger(ClaudeProvider.name);
  readonly name  = 'claude';
  readonly model = 'claude-3-5-haiku-20241022';

  private readonly apiKey: string | undefined;
  private readonly maxTokens: number;

  constructor(private readonly config: ConfigService) {
    this.apiKey    = this.config.get<string>('ai.claudeKey');
    this.maxTokens = this.config.get<number>('ai.maxTokens') ?? 1024;
  }

  isAvailable(): boolean {
    return !!this.apiKey;
  }

  async analyze(input: AiAnalysisInput): Promise<AiAnalysisOutput> {
    if (!this.apiKey) {
      throw new Error('CLAUDE_API_KEY não configurada');
    }

    const prompt = this.buildPrompt(input);
    const start  = Date.now();

    try {
      const res = await axios.post(
        'https://api.anthropic.com/v1/messages',
        {
          model:      this.model,
          max_tokens: input.maxTokens ?? this.maxTokens,
          system:     'Você é um especialista em infraestrutura de scraping e sistemas distribuídos. Responda APENAS em JSON válido, sem markdown, sem texto fora do JSON.',
          messages: [{ role: 'user', content: prompt }],
        },
        {
          headers: {
            'x-api-key':         this.apiKey,
            'anthropic-version': '2023-06-01',
            'Content-Type':      'application/json',
          },
          timeout: 30_000,
        },
      );

      const text   = res.data.content?.[0]?.text ?? '{}';
      const parsed = this.parseResponse(text);
      const tokens = res.data.usage?.output_tokens ?? 0;

      this.logger.debug(`[claude] Diagnóstico em ${Date.now() - start}ms — ${tokens} tokens`);

      return {
        ...parsed,
        tokensUsed: tokens,
        provider:   this.name,
        model:      this.model,
      };
    } catch (err: any) {
      this.logger.error(`[claude] Erro na API: ${err.message}`);
      throw err;
    }
  }

  private buildPrompt(input: AiAnalysisInput): string {
    return `${input.context}\n\nPergunta: ${input.question}\n\nResponda em JSON com exatamente esta estrutura:\n{"rootCause":"string","severity":"low|medium|high|critical","confidence":0.0-1.0,"suggestions":["string","string"],"estimatedRecoveryMinutes":30}`;
  }

  private parseResponse(text: string): Omit<AiAnalysisOutput, 'tokensUsed' | 'provider' | 'model'> {
    try {
      // Extrai JSON mesmo se vier com texto ao redor
      const match = text.match(/\{[\s\S]*\}/);
      const json  = JSON.parse(match?.[0] ?? text);

      return {
        rootCause:    json.rootCause   ?? 'Causa raiz não identificada',
        suggestions:  Array.isArray(json.suggestions) ? json.suggestions : [],
        severity:     json.severity    ?? 'medium',
        confidence:   Number(json.confidence ?? 0.5),
        estimatedRecoveryMinutes: json.estimatedRecoveryMinutes,
      };
    } catch {
      return {
        rootCause:    'Falha ao parsear resposta da IA',
        suggestions:  ['Verificar logs manualmente'],
        severity:     'medium',
        confidence:   0,
        estimatedRecoveryMinutes: undefined,
      };
    }
  }
}
