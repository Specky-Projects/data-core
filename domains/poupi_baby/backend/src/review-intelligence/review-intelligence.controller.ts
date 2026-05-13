import { Controller, Get, Post, Param, Body, UseGuards } from '@nestjs/common';
import { AuthGuard } from '@nestjs/passport';
import { ReviewIntelligenceService } from './review-intelligence.service';
import type { ReviewData } from './review-intelligence.service';

@Controller('review-intelligence')
export class ReviewIntelligenceController {
  constructor(private readonly service: ReviewIntelligenceService) {}

  /** Busca sumário de reviews de um produto (todos os marketplaces) */
  @UseGuards(AuthGuard('jwt'))
  @Get('product/:productId')
  getByProduct(@Param('productId') productId: string) {
    return this.service.getByProduct(productId);
  }

  /**
   * Processa reviews manualmente (para testes / ingestão externa).
   * Em produção, chamado pelo scraper de reviews via job.
   */
  @UseGuards(AuthGuard('jwt'))
  @Post('process')
  processReviews(@Body() data: ReviewData) {
    return this.service.processReviews(data);
  }
}
