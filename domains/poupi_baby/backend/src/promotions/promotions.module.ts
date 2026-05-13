import { Module } from '@nestjs/common';
import { PromotionsService } from './promotions.service';
import { PromotionsScheduler } from './promotions.scheduler';
import { PrismaModule } from '../prisma/prisma.module';
import { AffiliateModule } from '../affiliate/affiliate.module';

@Module({
  imports: [PrismaModule, AffiliateModule],
  providers: [PromotionsService, PromotionsScheduler],
  exports: [PromotionsService],
})
export class PromotionsModule {}
