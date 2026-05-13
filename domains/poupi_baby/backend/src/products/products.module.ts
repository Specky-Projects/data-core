import { Module } from '@nestjs/common';

import { PrismaModule } from '../prisma/prisma.module';
import { ProductsController } from './products.controller';
import { ProductsService } from './products.service';
import { ProductMatchingService } from './matching/product-matching.service';
import { ProductNormalizerService } from './matching/product-normalizer.service';

@Module({
  imports: [PrismaModule],
  controllers: [ProductsController],
  providers: [ProductsService, ProductMatchingService, ProductNormalizerService],
  exports: [ProductsService, ProductMatchingService, ProductNormalizerService],
})
export class ProductsModule {}
