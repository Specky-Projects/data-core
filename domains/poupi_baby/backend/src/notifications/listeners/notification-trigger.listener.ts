/**
 * notification-trigger.listener.ts
 *
 * Ouve eventos de domínio e enfileira notificações correspondentes.
 *
 * Reage a:
 *   alert.triggered         → email de alerta de preço para o usuário
 *   deal.score_high         → email de deal score alto (se usuário tem alerta ativo)
 *   review.trust_score_changed → email de trust score baixo (< 30)
 *   ai-ops.incident_detected   → email para admin
 */

import { Injectable, Logger } from '@nestjs/common';
import { OnEvent } from '@nestjs/event-emitter';
import { PrismaService } from '../../prisma/prisma.service';
import { NotificationQueueService } from '../queue/notification-queue.service';
import { DOMAIN_EVENTS } from '../../shared/events/domain-events';
import type {
  AlertTriggeredPayload,
  IncidentDetectedPayload,
} from '../../shared/events/domain-events';

@Injectable()
export class NotificationTriggerListener {
  private readonly logger = new Logger(NotificationTriggerListener.name);

  constructor(
    private readonly prisma:             PrismaService,
    private readonly notificationQueue:  NotificationQueueService,
  ) {}

  // ── Alerta de preço disparado ─────────────────────────────────────────────

  @OnEvent(DOMAIN_EVENTS.ALERT_TRIGGERED)
  async handleAlertTriggered(event: { payload: AlertTriggeredPayload }): Promise<void> {
    const { alertId, userId, productId, marketplace, currentPrice, targetPrice } = event.payload;

    try {
      // Busca dados do usuário + produto para montar o email
      const [user, product, offer] = await Promise.all([
        this.prisma.user.findUnique({ where: { id: userId }, select: { name: true, email: true } }),
        this.prisma.product.findUnique({ where: { id: productId }, select: { title: true, imageUrl: true } }),
        this.prisma.offer.findFirst({
          where: {
            productId,
            availability: true,
            marketplace:  { name: { equals: marketplace, mode: 'insensitive' } },
          },
          orderBy: { price: 'asc' },
          select: { productUrl: true, price: true },
        }),
      ]);

      if (!user || !product || !offer) {
        this.logger.warn(`[notification-trigger] Dados insuficientes para alertId=${alertId}`);
        return;
      }

      await this.notificationQueue.sendPriceAlert({
        userId,
        email:           user.email,
        userName:        user.name,
        productTitle:    product.title,
        productUrl:      offer.productUrl,
        productImageUrl: product.imageUrl,
        currentPrice,
        previousPrice:   Number(offer.price),
        targetPrice,
        marketplace,
      });
    } catch (err: any) {
      this.logger.error(`[notification-trigger] Erro em alert.triggered: ${err.message}`);
    }
  }

  // ── Deal Score alto ───────────────────────────────────────────────────────

  @OnEvent(DOMAIN_EVENTS.DEAL_SCORE_HIGH)
  async handleDealScoreHigh(event: { payload: {
    offerId:      string;
    productId:    string;
    score:        number;
    label:        string;
    currentPrice: number;
    discountVsAvg: number | null;
  }}): Promise<void> {
    const { productId, score, label, currentPrice, discountVsAvg } = event.payload;

    try {
      // Notifica usuários que têm alertas ativos para este produto
      const alerts = await this.prisma.alert.findMany({
        where:   { productId, active: true },
        include: {
          user:    { select: { email: true, name: true } },
          product: { select: { title: true } },
        },
      });

      const offer = await this.prisma.offer.findFirst({
        where:   { productId, availability: true },
        orderBy: { price: 'asc' },
        select:  { productUrl: true },
      });

      for (const alert of alerts) {
        // Só notifica se o score for melhor que o deal anterior (evita spam)
        await this.notificationQueue.sendDealHighScore({
          userId:       alert.userId,
          email:        alert.user.email,
          productTitle: alert.product.title,
          productUrl:   offer?.productUrl ?? '',
          score,
          label,
          currentPrice,
          discountVsAvg,
        });
      }

      if (alerts.length > 0) {
        this.logger.debug(
          `[notification-trigger] deal.score_high — ${alerts.length} usuários notificados`,
        );
      }
    } catch (err: any) {
      this.logger.error(`[notification-trigger] Erro em deal.score_high: ${err.message}`);
    }
  }

  // ── Trust Score baixo ─────────────────────────────────────────────────────

  @OnEvent(DOMAIN_EVENTS.TRUST_SCORE_CHANGED)
  async handleTrustScoreChanged(event: { payload: {
    productId:   string;
    marketplace: string;
    oldScore:    number;
    newScore:    number;
  }}): Promise<void> {
    const { productId, marketplace, oldScore, newScore } = event.payload;

    // Só notifica quando a queda é severa (score baixou para zona de risco)
    if (newScore >= 30 || newScore >= oldScore) return;

    try {
      const product = await this.prisma.product.findUnique({
        where:   { id: productId },
        select:  { title: true },
      });

      if (!product) return;

      // Busca usuários com alerta ativo para este produto
      const alerts = await this.prisma.alert.findMany({
        where:   { productId, active: true },
        include: { user: { select: { email: true, name: true } } },
      });

      for (const alert of alerts) {
        await this.notificationQueue.send({
          userId:   alert.userId,
          channel:  'email',
          template: 'trust.low_score',
          payload:  {
            email:        alert.user.email,
            productTitle: product.title,
            marketplace,
            trustScore:   newScore,
            trustLabel:   newScore < 20 ? 'Suspeito' : 'Baixo',
          },
          priority: 'low',
        });
      }
    } catch (err: any) {
      this.logger.error(`[notification-trigger] Erro em trust_score_changed: ${err.message}`);
    }
  }

  // ── Incidente de scraping (admin) ─────────────────────────────────────────

  @OnEvent(DOMAIN_EVENTS.INCIDENT_DETECTED)
  async handleIncidentDetected(event: { payload: IncidentDetectedPayload }): Promise<void> {
    const { incidentId, marketplace, severity } = event.payload;

    // Só pinga o admin para severity high/critical
    if (!['high', 'critical'].includes(severity)) return;

    try {
      const incident = await this.prisma.aiIncident.findUnique({
        where:  { id: incidentId },
        select: { rootCause: true, suggestions: true },
      });

      if (!incident) return;

      await this.notificationQueue.sendAdminIncidentAlert({
        incidentId,
        marketplace,
        severity,
        rootCause:   incident.rootCause ?? 'Causa desconhecida',
        suggestions: this.parseJson<string[]>(incident.suggestions, []),
      });
    } catch (err: any) {
      this.logger.error(`[notification-trigger] Erro em incident_detected: ${err.message}`);
    }
  }

  private parseJson<T>(str: string | null, fallback: T): T {
    if (!str) return fallback;
    try { return JSON.parse(str); } catch { return fallback; }
  }
}
