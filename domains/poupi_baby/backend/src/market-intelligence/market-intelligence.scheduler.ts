/**
 * market-intelligence.scheduler.ts
 *
 * Agenda análises automáticas de padrões de mercado.
 *
 * Crons:
 *   - A cada hora: analisa produtos com scraping recente (últimas 2h)
 *   - Toda madrugada (03:00): análise completa dos últimas 24h
 */

import { Injectable, Logger } from '@nestjs/common';
import { Cron, CronExpression } from '@nestjs/schedule';
import { MarketIntelligenceService } from './market-intelligence.service';

@Injectable()
export class MarketIntelligenceScheduler {
  private readonly logger = new Logger(MarketIntelligenceScheduler.name);

  constructor(private readonly service: MarketIntelligenceService) {}

  /** Análise leve: produtos scraped nas últimas 2h */
  @Cron(CronExpression.EVERY_HOUR)
  async hourlyAnalysis() {
    this.logger.log('[scheduler] Iniciando análise horária de padrões...');
    const count = await this.service.analyzeRecent(2);
    this.logger.log(`[scheduler] Análise horária: ${count} produtos processados`);
  }

  /** Análise completa: todos os produtos das últimas 24h */
  @Cron('0 3 * * *') // 03:00 diariamente
  async dailyFullAnalysis() {
    this.logger.log('[scheduler] Iniciando análise diária completa de padrões...');
    const count = await this.service.analyzeRecent(24);
    this.logger.log(`[scheduler] Análise diária: ${count} produtos processados`);
  }
}
