import { Controller, Get, Param, Query, UseGuards } from '@nestjs/common';
import { AuthGuard } from '@nestjs/passport';
import { PriceHistoryService } from './price-history.service';

@UseGuards(AuthGuard('jwt'))
@Controller('price-history')
export class PriceHistoryController {
  constructor(private readonly svc: PriceHistoryService) {}

  /** GET /price-history/product/:productId?days=90 */
  @Get('product/:productId')
  findByProduct(
    @Param('productId') productId: string,
    @Query('days') days?: string,
  ) {
    return this.svc.findByProduct(productId, days ? Number(days) : undefined);
  }

  /** GET /price-history/product/:productId/summary */
  @Get('product/:productId/summary')
  productSummary(@Param('productId') productId: string) {
    return this.svc.getProductSummary(productId);
  }

  /** GET /price-history/offer/:offerId */
  @Get('offer/:offerId')
  findByOffer(
    @Param('offerId') offerId: string,
    @Query('limit') limit?: string,
    @Query('skip') skip?: string,
  ) {
    return this.svc.findByOffer(offerId, limit ? Number(limit) : undefined, skip ? Number(skip) : undefined);
  }

  /** GET /price-history/offer/:offerId/summary */
  @Get('offer/:offerId/summary')
  offerSummary(@Param('offerId') offerId: string) {
    return this.svc.getSummary(offerId);
  }

  /** GET /price-history?limit=&skip= (admin) */
  @Get()
  findAll(@Query('limit') limit?: string, @Query('skip') skip?: string) {
    return this.svc.findAll(limit ? Number(limit) : undefined, skip ? Number(skip) : undefined);
  }
}
