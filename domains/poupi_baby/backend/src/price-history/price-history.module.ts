import { Module } from '@nestjs/common';

import { PrismaModule } from '../prisma/prisma.module';

import { PriceHistoryController } from './price-history.controller';
import { PriceHistoryService } from './price-history.service';

@Module({
  imports: [PrismaModule],
  controllers: [PriceHistoryController],
  providers: [PriceHistoryService],
  exports: [PriceHistoryService],
})
export class PriceHistoryModule {}