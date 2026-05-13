/**
 * billing.service.ts
 *
 * Orquestra pagamentos e assinaturas:
 *   - Seleciona o gateway correto via factory (MP > Stripe > Mock)
 *   - Ativa/cancela assinaturas premium no banco
 *   - Processa eventos de webhook normalizados
 */

import { Injectable, Logger } from '@nestjs/common';
import { SubscriptionPlan } from '@prisma/client';
import { PrismaService } from '../prisma/prisma.service';
import { PlansService } from '../plans/plans.service';
import { EventBusService } from '../shared/events/event-bus.service';
import { DOMAIN_EVENTS } from '../shared/events/domain-events';
import { PaymentGateway } from './gateways/gateway.interface';
import { MercadoPagoGateway } from './gateways/mercadopago.gateway';
import { StripeGateway } from './gateways/stripe.gateway';
import { MockGateway } from './gateways/mock.gateway';
import { getPlan } from '../plans/plans.config';

@Injectable()
export class BillingService {
  private readonly logger = new Logger(BillingService.name);
  private readonly gateway: PaymentGateway;

  constructor(
    private prisma:       PrismaService,
    private plansService: PlansService,
    private eventBus:     EventBusService,
  ) {
    this.gateway = this.selectGateway();
    this.logger.log(`Gateway de pagamento ativo: ${this.gateway.provider}`);
  }

  // -------------------------------------------------------------------------
  // Factory de gateway
  // -------------------------------------------------------------------------

  private selectGateway(): PaymentGateway {
    if (process.env.MP_ACCESS_TOKEN) return new MercadoPagoGateway();
    if (process.env.STRIPE_SECRET_KEY) return new StripeGateway();
    this.logger.warn('Nenhum gateway configurado — usando MockGateway (apenas desenvolvimento)');
    return new MockGateway();
  }

  get activeProvider(): string {
    return this.gateway.provider;
  }

  // -------------------------------------------------------------------------
  // Checkout
  // -------------------------------------------------------------------------

  async createCheckout(userId: string, planId: string) {
    const plan = getPlan(planId);
    if (!plan || planId === 'free') {
      throw new Error('Plano inválido para checkout');
    }

    return this.gateway.createCheckout(userId, planId, plan.priceBrl);
  }

  // -------------------------------------------------------------------------
  // Webhook
  // -------------------------------------------------------------------------

  validateWebhook(payload: Buffer | string, signature: string): boolean {
    return this.gateway.validateWebhook(payload, signature);
  }

  async handleWebhook(payload: unknown): Promise<void> {
    const event = await this.gateway.parseWebhook(payload);
    if (!event) return;

    this.logger.log(`Webhook recebido: ${event.eventType} — user: ${event.userId}`);

    switch (event.eventType) {
      case 'payment.approved':
        await this.activatePremium(event.userId, event.paymentId, event.provider);
        break;
      case 'payment.cancelled':
      case 'payment.refunded':
      case 'subscription.cancelled':
        await this.deactivatePremium(event.userId, event.eventType);
        break;
    }
  }

  // -------------------------------------------------------------------------
  // Ativação / Desativação
  // -------------------------------------------------------------------------

  async activatePremium(userId: string, paymentId: string, provider: string, months = 1): Promise<void> {
    const existing = await this.prisma.subscription.findFirst({
      where: { userId, status: 'active', plan: SubscriptionPlan.premium },
    });

    const expiresAt = existing?.expiresAt
      ? new Date(existing.expiresAt.getTime() + months * 30 * 86_400_000)
      : new Date(Date.now() + months * 30 * 86_400_000);

    const isUpgrade = !existing; // primeira ativação = upgrade do free

    if (existing) {
      await this.prisma.subscription.update({
        where: { id: existing.id },
        data: { expiresAt },
      });
    } else {
      await this.prisma.subscription.create({
        data: {
          userId,
          plan: SubscriptionPlan.premium,
          status: 'active',
          provider,
          providerSubscriptionId: paymentId,
          expiresAt,
        },
      });
    }

    this.logger.log(`Premium ativado para ${userId} até ${expiresAt.toISOString()}`);

    this.eventBus.emit(DOMAIN_EVENTS.SUBSCRIPTION_ACTIVATED, {
      userId,
      planId: 'premium',
    });

    if (isUpgrade) {
      this.eventBus.emit(DOMAIN_EVENTS.PLAN_UPGRADED, {
        userId,
        planId:  'premium',
        oldPlan: 'free',
      });
    }
  }

  async deactivatePremium(userId: string, reason: string): Promise<void> {
    await this.prisma.subscription.updateMany({
      where: { userId, status: 'active', plan: SubscriptionPlan.premium },
      data: { status: 'canceled' },
    });

    this.logger.log(`Premium desativado para ${userId}: ${reason}`);

    this.eventBus.emit(DOMAIN_EVENTS.SUBSCRIPTION_CANCELLED, {
      userId,
      planId: 'premium',
    });
  }

  async cancelSubscription(userId: string, subscriptionId: string): Promise<void> {
    await this.gateway.cancelSubscription(subscriptionId);
    await this.deactivatePremium(userId, 'Cancelado pelo usuário');
  }

  // -------------------------------------------------------------------------
  // Status
  // -------------------------------------------------------------------------

  async getStatus(userId: string) {
    return this.plansService.getSubscriptionStatus(userId);
  }
}
