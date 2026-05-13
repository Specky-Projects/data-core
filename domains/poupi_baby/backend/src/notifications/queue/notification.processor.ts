import { Processor, WorkerHost } from '@nestjs/bullmq';
import { Logger } from '@nestjs/common';
import { Job } from 'bullmq';
import { NotificationsService } from '../notifications.service';
import {
  NOTIFICATION_QUEUE,
  NOTIFICATION_JOB,
  NotificationJobData,
} from '../../shared/queues/queue.constants';

/**
 * NotificationProcessor — despacha notificações de forma assíncrona.
 *
 * Templates suportados:
 *   alert.triggered   — alerta de queda de preço atingido
 *   deal.high_score   — produto com deal score alto (≥75)
 *   trust.low_score   — produto com trust score baixo (review bombing, etc.)
 *   incident.detected — incidente de scraping detectado (admin)
 */
@Processor(NOTIFICATION_QUEUE)
export class NotificationProcessor extends WorkerHost {
  private readonly logger = new Logger(NotificationProcessor.name);

  constructor(private readonly notificationsService: NotificationsService) {
    super();
  }

  async process(job: Job<NotificationJobData>): Promise<void> {
    if (job.name !== NOTIFICATION_JOB) return;

    const { userId, channel, template, payload } = job.data;

    this.logger.debug(
      `[notification] Enviando — template=${template} channel=${channel} userId=${userId ?? 'admin'}`,
    );

    try {
      await this.dispatch(channel, template, payload);
    } catch (err: any) {
      this.logger.error(
        `[notification] Erro no job ${job.id} (${template}): ${err.message}`,
      );
      throw err; // BullMQ faz retry
    }
  }

  // ── Dispatch por template ────────────────────────────────────────────────

  private async dispatch(
    channel: NotificationJobData['channel'],
    template: string,
    payload: Record<string, unknown>,
  ): Promise<void> {
    if (channel === 'email') {
      await this.dispatchEmail(template, payload);
    } else {
      // push e webhook: log por enquanto — expandir com FCM/Webhook
      this.logger.log(
        `[notification] canal=${channel} template=${template} payload=${JSON.stringify(payload)}`,
      );
    }
  }

  private async dispatchEmail(
    template: string,
    payload: Record<string, unknown>,
  ): Promise<void> {
    switch (template) {
      case 'alert.triggered':
        await this.notificationsService.sendPriceAlert(payload as any);
        break;

      case 'alert.smart':
        await this.notificationsService.sendSmartAlert(payload as any);
        break;

      case 'deal.high_score':
        await this.notificationsService.sendDealHighScore(payload as any);
        break;

      case 'trust.low_score':
        await this.notificationsService.sendTrustLowScore(payload as any);
        break;

      case 'incident.detected':
        await this.notificationsService.sendIncidentAlert(payload as any);
        break;

      default:
        this.logger.warn(`[notification] Template desconhecido: ${template}`);
    }
  }
}
