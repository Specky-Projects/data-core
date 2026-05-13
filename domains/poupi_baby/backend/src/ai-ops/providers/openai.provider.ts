import { Injectable, Logger } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import axios from 'axios';
import { IAiProvider, AiAnalysisInput, AiAnalysisOutput } from './ai-provider.interface';

@Injectable()
export class OpenAIProvider implements IAiProvider {
  private readonly logger = new Logger(OpenAIProvider.name);
  readonly name  = 'openai';
  readonly model = 'gpt-4o-mini';

  private readonly apiKey: string | undefined;
  private readonly maxTokens: number;

  constructor(private readonly config: ConfigService) {
    this.apiKey    = this.config.get<string>('ai.openaiKey');
    this.maxTokens = this.config.get<number>('ai.maxTokens') ?? 1024;
  }

  isAvailable(): boolean {
    return !!this.apiKey;
  }

  async analyze(input: AiAnalysisInput): Promise<AiAnalysisOutput> {
    if (!this.apiKey) throw new Error('OPENAI_API_KEY não configurada');

    const start = Date.now();
    try {
      const res = await axios.post(
        'https://api.openai.com/v1/chat/completions',
        {
          model:      this.model,
          max_tokens: input.maxTokens ?? this.maxTokens,
          response_format: { type: 'json_object' },
          messages: [
            {
              role:    'system',
              content: 'Você é um especialista em infraestrutura de scraping e sistemas distribuídos. Responda APENAS em JSON válido.',
            },
            {
              role:    'user',
              content: `${input.context}\n\nPergunta: ${input.question}\n\nResponda em JSON: {"rootCause":"string","severity":"low|medium|high|critical","confidence":0.0-1.0,"suggestions":["string"],"estimatedRecoveryMinutes":30}`,
            },
          ],
        },
        {
          headers: {
            'Authorization': `Bearer ${this.apiKey}`,
            'Content-Type':  'application/json',
          },
          timeout: 30_000,
        },
      );

      const text   = res.data.choices?.[0]?.message?.content ?? '{}';
      const tokens = res.data.usage?.completion_tokens ?? 0;
      const json   = JSON.parse(text);

      this.logger.debug(`[openai] Diagnóstico em ${Date.now() - start}ms — ${tokens} tokens`);

      return {
        rootCause:    json.rootCause   ?? 'Causa raiz não identificada',
        suggestions:  Array.isArray(json.suggestions) ? json.suggestions : [],
        severity:     json.severity    ?? 'medium',
        confidence:   Number(json.confidence ?? 0.5),
        estimatedRecoveryMinutes: json.estimatedRecoveryMinutes,
        tokensUsed:   tokens,
        provider:     this.name,
        model:        this.model,
      };
    } catch (err: any) {
      this.logger.error(`[openai] Erro na API: ${err.message}`);
      throw err;
    }
  }
}
