import { Module } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { PrismaModule } from '../prisma/prisma.module';

import { MockAiProvider }   from './providers/mock.provider';
import { ClaudeProvider }   from './providers/claude.provider';
import { OpenAIProvider }   from './providers/openai.provider';
import { AI_PROVIDER_TOKEN } from './providers/ai-provider.interface';

import { IncidentService }  from './incidents/incident.service';
import { IncidentDetector } from './incidents/incident.detector';
import { IncidentAnalyzer } from './analyzers/incident.analyzer';
import { AiOpsController }  from './ai-ops.controller';

/**
 * AiOpsModule — sistema de diagnóstico autônomo de incidentes.
 *
 * Provider de IA selecionado via env AI_PROVIDER:
 *   - 'claude'  → ClaudeProvider (CLAUDE_API_KEY obrigatório)
 *   - 'openai'  → OpenAIProvider (OPENAI_API_KEY obrigatório)
 *   - 'mock'    → MockAiProvider (padrão, sem custo)
 *
 * Exporta IncidentDetector para que o CrawlerModule possa
 * chamar evaluate() após cada tentativa de scraping.
 */
@Module({
  imports: [PrismaModule],
  controllers: [AiOpsController],
  providers: [
    // Providers de IA (todos instanciados, um selecionado via factory)
    MockAiProvider,
    ClaudeProvider,
    OpenAIProvider,

    // Factory: seleciona o provider baseado na config
    {
      provide:    AI_PROVIDER_TOKEN,
      inject:     [ConfigService, MockAiProvider, ClaudeProvider, OpenAIProvider],
      useFactory: (
        config:  ConfigService,
        mock:    MockAiProvider,
        claude:  ClaudeProvider,
        openai:  OpenAIProvider,
      ) => {
        const provider = config.get<string>('ai.provider') ?? 'mock';
        if (provider === 'claude' && claude.isAvailable())  return claude;
        if (provider === 'openai' && openai.isAvailable())  return openai;
        if (provider !== 'mock') {
          console.warn(
            `[ai-ops] Provider "${provider}" indisponível (API key ausente) — usando mock.`,
          );
        }
        return mock;
      },
    },

    IncidentService,
    IncidentAnalyzer,
    IncidentDetector,
  ],
  exports: [
    IncidentDetector,
    IncidentService,
    IncidentAnalyzer,
  ],
})
export class AiOpsModule {}
