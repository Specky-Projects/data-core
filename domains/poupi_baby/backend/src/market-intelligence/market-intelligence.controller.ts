import {
  Controller,
  Get,
  Post,
  Param,
  Query,
  UseGuards,
  ParseIntPipe,
  DefaultValuePipe,
  ParseFloatPipe,
} from '@nestjs/common';
import { AuthGuard } from '@nestjs/passport';
import { MarketIntelligenceService } from './market-intelligence.service';

@Controller('market-intelligence')
@UseGuards(AuthGuard('jwt'))
export class MarketIntelligenceController {
  constructor(private readonly service: MarketIntelligenceService) {}

  /** Padrão de um produto+marketplace específico */
  @Get('product/:productId/:marketplace')
  getPattern(
    @Param('productId') productId: string,
    @Param('marketplace') marketplace: string,
  ) {
    return this.service.getPattern(productId, marketplace);
  }

  /** Todos os padrões de um produto (todos os marketplaces) */
  @Get('product/:productId')
  getAllPatterns(@Param('productId') productId: string) {
    return this.service.getAllPatterns(productId);
  }

  /** Produtos com tendência de queda de preço */
  @Get('trends/downward')
  getDownwardTrends(
    @Query('minStrength', new DefaultValuePipe(0.3), ParseFloatPipe) minStrength: number,
    @Query('limit', new DefaultValuePipe(50), ParseIntPipe) limit: number,
  ) {
    return this.service.getDownwardTrends(minStrength, limit);
  }

  /** Produtos com promoção estimada nas próximas N horas */
  @Get('promos/upcoming')
  getUpcomingPromos(
    @Query('withinHours', new DefaultValuePipe(72), ParseIntPipe) withinHours: number,
    @Query('limit', new DefaultValuePipe(50), ParseIntPipe) limit: number,
  ) {
    return this.service.getUpcomingPromos(withinHours, limit);
  }

  /** Força re-análise de um produto+marketplace (admin/debug) */
  @Post('analyze/:productId/:marketplace')
  analyzeProduct(
    @Param('productId') productId: string,
    @Param('marketplace') marketplace: string,
  ) {
    return this.service.analyzeProduct(productId, marketplace);
  }

  /** Força re-análise de todos os produtos recentes (admin/debug) */
  @Post('analyze/recent')
  analyzeRecent(
    @Query('hoursBack', new DefaultValuePipe(24), ParseIntPipe) hoursBack: number,
  ) {
    return this.service.analyzeRecent(hoursBack);
  }
}
