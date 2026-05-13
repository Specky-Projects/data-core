import { Controller, Get, Param, UseGuards } from '@nestjs/common';
import { AuthGuard } from '@nestjs/passport';
import { DealScoreService } from './deal-score.service';

@UseGuards(AuthGuard('jwt'))
@Controller('deal-score')
export class DealScoreController {
  constructor(private readonly service: DealScoreService) {}

  /** GET /deal-score/offer/:offerId — score de uma oferta */
  @Get('offer/:offerId')
  getOfferScore(@Param('offerId') offerId: string) {
    return this.service.calculate(offerId);
  }

  /** GET /deal-score/product/:productId — melhor score entre as ofertas do produto */
  @Get('product/:productId')
  getProductScore(@Param('productId') productId: string) {
    return this.service.calculateForProduct(productId);
  }
}
