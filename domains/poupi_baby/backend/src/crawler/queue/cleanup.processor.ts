import { Processor, WorkerHost } from '@nestjs/bullmq';
import { Logger } from '@nestjs/common';
import { Job } from 'bullmq';
import { PrismaService } from '../../prisma/prisma.service';
import { ScraperHealthService } from '../scraper-health.service';
import {
  CLEANUP_QUEUE,
  CLEANUP_METRICS_JOB,
  CLEANUP_EVENTS_JOB,
  CLEANUP_INCIDENTS_JOB,
  CleanupJobData,
} from '../../shared/queues/queue.constants';

@Processor(CLEANUP_QUEUE)
export class CleanupProcessor extends WorkerHost {
  private readonly logger = new Logger(CleanupProcessor.name);

  constructor(
    private readonly prisma:  PrismaService,
    private readonly health:  ScraperHealthService,
  ) {
    super();
  }

  async process(job: Job<CleanupJobData>): Promise<void> {
    switch (job.name) {
      case CLEANUP_METRICS_JOB:
        return this.cleanupScraperMetrics(job.data.retentionDays);
      case CLEANUP_EVENTS_JOB:
        return this.cleanupUserEvents(job.data.retentionDays);
      case CLEANUP_INCIDENTS_JOB:
        return this.cleanupAiIncidents(job.data.retentionDays);
      default:
        this.logger.warn(`[cleanup] Job desconhecido: ${job.name}`);
    }
  }

  private async cleanupScraperMetrics(retentionDays: number): Promise<void> {
    const removed = await this.health.pruneOldMetrics();
    this.logger.log(`[cleanup] ScraperMetrics: ${removed} registros removidos (>${retentionDays}d)`);
  }

  private async cleanupUserEvents(retentionDays: number): Promise<void> {
    const cutoff = new Date();
    cutoff.setDate(cutoff.getDate() - retentionDays);

    const { count } = await this.prisma.userEvent.deleteMany({
      where: { occurredAt: { lt: cutoff } },
    });
    this.logger.log(`[cleanup] UserEvents: ${count} registros removidos (>${retentionDays}d)`);
  }

  private async cleanupAiIncidents(retentionDays: number): Promise<void> {
    const cutoff = new Date();
    cutoff.setDate(cutoff.getDate() - retentionDays);

    const { count } = await this.prisma.aiIncident.deleteMany({
      where: {
        createdAt: { lt: cutoff },
        status: { in: ['resolved', 'acknowledged'] },
      },
    });
    this.logger.log(`[cleanup] AiIncidents: ${count} registros removidos (>${retentionDays}d)`);
  }
}
