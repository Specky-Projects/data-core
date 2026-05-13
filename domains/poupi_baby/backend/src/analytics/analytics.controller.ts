import {
  Controller,
  Get,
  Post,
  Body,
  Query,
  UseGuards,
  ParseIntPipe,
  DefaultValuePipe,
} from '@nestjs/common';
import { AuthGuard } from '@nestjs/passport';
import { AnalyticsService } from './analytics.service';
import type { TrackEventInput } from './analytics.service';

@Controller('analytics')
@UseGuards(AuthGuard('jwt'))
export class AnalyticsController {
  constructor(private readonly service: AnalyticsService) {}

  /** Track manual de evento (usado pelo frontend via API route) */
  @Post('track')
  async track(@Body() body: TrackEventInput): Promise<{ ok: boolean }> {
    await this.service.track(body);
    return { ok: true };
  }

  /** Contagem de eventos por tipo — dashboard admin */
  @Get('event-counts')
  getEventCounts(
    @Query('days', new DefaultValuePipe(7), ParseIntPipe) days: number,
  ) {
    return this.service.getEventCounts(days);
  }

  /** Usuários únicos ativos */
  @Get('active-users')
  getActiveUsers(
    @Query('days', new DefaultValuePipe(30), ParseIntPipe) days: number,
  ) {
    return this.service.getActiveUsers(days).then((count) => ({ count, days }));
  }

  /** Produtos mais visualizados */
  @Get('top-products')
  getTopProducts(
    @Query('days', new DefaultValuePipe(7), ParseIntPipe)    days: number,
    @Query('limit', new DefaultValuePipe(20), ParseIntPipe)  limit: number,
  ) {
    return this.service.getTopProducts(days, limit);
  }

  /** Funil de conversão */
  @Get('funnel')
  getConversionFunnel(
    @Query('days', new DefaultValuePipe(30), ParseIntPipe) days: number,
  ) {
    return this.service.getConversionFunnel(days);
  }

  /** Série temporal de um evento para gráfico */
  @Get('time-series')
  getTimeSeries(
    @Query('eventType') eventType: string,
    @Query('days', new DefaultValuePipe(30), ParseIntPipe) days: number,
  ) {
    return this.service.getTimeSeries(eventType, days);
  }
}
