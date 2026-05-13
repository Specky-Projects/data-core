import { Module } from '@nestjs/common';

import { PrismaModule } from '../prisma/prisma.module';

import { MarketplacesController } from './marketplaces.controller';
import { MarketplacesService } from './marketplaces.service';

@Module({
  imports: [PrismaModule],
  controllers: [MarketplacesController],
  providers: [MarketplacesService],
})
export class MarketplacesModule {}