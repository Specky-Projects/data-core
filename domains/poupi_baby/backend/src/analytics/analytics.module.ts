import { Module } from '@nestjs/common';
import { PrismaModule } from '../prisma/prisma.module';
import { AnalyticsService }        from './analytics.service';
import { AnalyticsController }     from './analytics.controller';
import { AnalyticsEventsListener } from './listeners/analytics-events.listener';

@Module({
  imports:     [PrismaModule],
  controllers: [AnalyticsController],
  providers:   [AnalyticsService, AnalyticsEventsListener],
  exports:     [AnalyticsService],
})
export class AnalyticsModule {}
