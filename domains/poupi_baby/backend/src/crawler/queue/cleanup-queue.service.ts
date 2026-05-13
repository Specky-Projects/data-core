import { Injectable, Logger } from '@nestjs/common';
import { InjectQueue } from '@nestjs/bullmq';
import { Cron } from '@nestjs/schedule';
import { Queue } from 'bullmq';
import {
  CLEANUP_QUEUE,
  CLEANUP_METRICS_JOB,
  CLEANUP_EVENTS_JOB,
  CLEANUP_INCIDENTS_JOB,
} from '../../shared/queues/queue.constants';

@Injectable()
export class CleanupQueueService {
  private readonly logger = new Logger(CleanupQueueService.name);

  constructor(
    @InjectQueue(CLEANUP_QUEUE) private readonly queue: Queue,
  ) {}

  /** Agenda todos os jobs de cleanup — todo dia às 04:00 */
  @Cron('0 4 * * *')
  async scheduleDailyCleanup(): Promise<void> {
    this.logger.log('[cleanup] Agendando jobs de limpeza diária...');

    await this.queue.addBulk([
      {
        name: CLEANUP_METRICS_JOB,
        data: { type: 'scraper-metrics', retentionDays: 30 },
        opts: { jobId: `cleanup-metrics-${this.today()}` },
      },
      {
        name: CLEANUP_EVENTS_JOB,
        data: { type: 'user-events', retentionDays: 90 },
        opts: { jobId: `cleanup-events-${this.today()}` },
      },
      {
        name: CLEANUP_INCIDENTS_JOB,
        data: { type: 'ai-incidents', retentionDays: 60 },
        opts: { jobId: `cleanup-incidents-${this.today()}` },
      },
    ]);
  }

  private today(): string {
    return new Date().toISOString().slice(0, 10);
  }
}
