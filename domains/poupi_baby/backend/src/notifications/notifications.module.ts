import { Module } from '@nestjs/common';
import { BullModule } from '@nestjs/bullmq';
import { PrismaModule } from '../prisma/prisma.module';
import { NotificationsService }          from './notifications.service';
import { NotificationQueueService }      from './queue/notification-queue.service';
import { NotificationProcessor }         from './queue/notification.processor';
import { NotificationTriggerListener }   from './listeners/notification-trigger.listener';
import {
  NOTIFICATION_QUEUE,
  NOTIFICATION_JOB_DEFAULTS,
} from '../shared/queues/queue.constants';

@Module({
  imports: [
    PrismaModule,
    BullModule.registerQueue({
      name:              NOTIFICATION_QUEUE,
      defaultJobOptions: NOTIFICATION_JOB_DEFAULTS,
    }),
  ],
  providers: [
    NotificationsService,
    NotificationQueueService,
    NotificationProcessor,
    NotificationTriggerListener,
  ],
  exports: [NotificationsService, NotificationQueueService],
})
export class NotificationsModule {}
