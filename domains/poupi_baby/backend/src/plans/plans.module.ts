import { Module } from '@nestjs/common';
import { PlansService } from './plans.service';
import { PrismaModule } from '../prisma/prisma.module';

@Module({
  imports: [PrismaModule],
  providers: [PlansService],
  exports: [PlansService],
})
export class PlansModule {}
