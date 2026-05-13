import { Module } from '@nestjs/common';
import { PrismaModule } from '../prisma/prisma.module';
import { NotificationsModule } from '../notifications/notifications.module';
import { AlertsController } from './alerts.controller';
import { AlertsService } from './alerts.service';
import { CheckAlertsService } from './check-alerts.service';
import { AlertEventsListener } from './listeners/alert-events.listener';

@Module({
  imports:     [PrismaModule, NotificationsModule],
  controllers: [AlertsController],
  providers:   [AlertsService, CheckAlertsService, AlertEventsListener],
  exports:     [AlertsService],
})
export class AlertsModule {}
