import { Injectable, Logger } from '@nestjs/common';
import { InjectQueue } from '@nestjs/bullmq';
import { Queue } from 'bullmq';
import {
  NOTIFICATION_QUEUE,
  NOTIFICATION_JOB,
  NotificationJobData,
} from '../../shared/queues/queue.constants';

@Injectable()
export class NotificationQueueService {
  private readonly logger = new Logger(NotificationQueueService.name);

  constructor(
    @InjectQueue(NOTIFICATION_QUEUE) private readonly queue: Queue,
  ) {}

  async send(data: NotificationJobData): Promise<void> {
    const priority = data.priority === 'high' ? 1 : data.priority === 'low' ? 50 : 10;

    await this.queue.add(NOTIFICATION_JOB, data, { priority });
    this.logger.debug(
      `[notification-queue] Enqueued template=${data.template} channel=${data.channel}`,
    );
  }

  /** Atalhos tipados por template */

  async sendPriceAlert(payload: {
    userId:       string;
    email:        string;
    userName:     string;
    productTitle: string;
    productUrl:   string;
    productImageUrl?: string | null;
    currentPrice: number;
    previousPrice: number;
    targetPrice:  number;
    marketplace:  string;
  }): Promise<void> {
    return this.send({
      userId:   payload.userId,
      channel:  'email',
      template: 'alert.triggered',
      payload:  payload as unknown as Record<string, unknown>,
      priority: 'high',
    });
  }

  async sendSmartAlert(payload: {
    userId:        string;
    email:         string;
    userName:      string;
    productTitle:  string;
    productUrl:    string;
    productImageUrl?: string | null;
    currentPrice:  number;
    previousPrice: number | null;
    marketplace:   string;
    type:          'NEW_LOWEST_PRICE' | 'PRICE_DROP' | 'RESTOCKED';
    reason:        string;
  }): Promise<void> {
    return this.send({
      userId:   payload.userId,
      channel:  'email',
      template: 'alert.smart',
      payload:  payload as unknown as Record<string, unknown>,
      priority: payload.type === 'RESTOCKED' ? 'normal' : 'high',
    });
  }

  async sendDealHighScore(payload: {
    userId?:      string;
    email:        string;
    productTitle: string;
    productUrl:   string;
    score:        number;
    label:        string;
    currentPrice: number;
    discountVsAvg: number | null;
  }): Promise<void> {
    return this.send({
      userId:   payload.userId,
      channel:  'email',
      template: 'deal.high_score',
      payload:  payload as unknown as Record<string, unknown>,
      priority: 'normal',
    });
  }

  async sendAdminIncidentAlert(payload: {
    incidentId:  string;
    marketplace: string;
    severity:    string;
    rootCause:   string;
    suggestions: string[];
  }): Promise<void> {
    return this.send({
      channel:  'email',
      template: 'incident.detected',
      payload:  payload as unknown as Record<string, unknown>,
      priority: 'high',
    });
  }
}
