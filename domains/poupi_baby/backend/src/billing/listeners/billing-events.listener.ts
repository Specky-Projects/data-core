/**
 * billing-events.listener.ts
 *
 * Reage a eventos de billing para manter o estado do usuário consistente.
 *
 * subscription_activated → log + futuro: provisionar recursos
 * subscription_cancelled → log + futuro: revogar acesso a features premium
 * plan_upgraded          → log + futuro: liberar novas features imediatamente
 */

import { Injectable, Logger } from '@nestjs/common';
import { OnEvent } from '@nestjs/event-emitter';
import { PrismaService } from '../../prisma/prisma.service';
import { DOMAIN_EVENTS } from '../../shared/events/domain-events';

interface BillingEventPayload {
  userId:  string;
  planId:  string;
  oldPlan?: string;
}

@Injectable()
export class BillingEventsListener {
  private readonly logger = new Logger(BillingEventsListener.name);

  constructor(private readonly prisma: PrismaService) {}

  @OnEvent(DOMAIN_EVENTS.SUBSCRIPTION_ACTIVATED)
  async handleSubscriptionActivated(event: { payload: BillingEventPayload }): Promise<void> {
    const { userId, planId } = event.payload;
    this.logger.log(`[billing-listener] Subscription ativada — userId=${userId} plan=${planId}`);

    // Placeholder: provisionar recursos (ex: criar slots de produto, etc.)
    // await this.provisionPlanResources(userId, planId);
  }

  @OnEvent(DOMAIN_EVENTS.SUBSCRIPTION_CANCELLED)
  async handleSubscriptionCancelled(event: { payload: BillingEventPayload }): Promise<void> {
    const { userId } = event.payload;
    this.logger.log(`[billing-listener] Subscription cancelada — userId=${userId}`);

    // Placeholder: revogar alertas excedentes do plano free
    // await this.enforceFreeLimits(userId);
  }

  @OnEvent(DOMAIN_EVENTS.PLAN_UPGRADED)
  async handlePlanUpgraded(event: { payload: BillingEventPayload }): Promise<void> {
    const { userId, planId, oldPlan } = event.payload;
    this.logger.log(
      `[billing-listener] Plano atualizado — userId=${userId} ${oldPlan} → ${planId}`,
    );

    // Placeholder: liberar features do novo plano imediatamente
    // await this.unlockPlanFeatures(userId, planId);
  }
}
