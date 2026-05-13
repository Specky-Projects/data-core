import { Module } from '@nestjs/common';
import { BillingService } from './billing.service';
import { BillingController } from './billing.controller';
import { BillingEventsListener } from './listeners/billing-events.listener';
import { PrismaModule } from '../prisma/prisma.module';
import { PlansModule } from '../plans/plans.module';

@Module({
  imports:     [PrismaModule, PlansModule],
  controllers: [BillingController],
  providers:   [BillingService, BillingEventsListener],
  exports:     [BillingService],
})
export class BillingModule {}
