/**
 * plans.service.ts
 *
 * Lógica de negócio relacionada a planos de assinatura:
 *   - Verificação de limites por plano
 *   - Status detalhado da assinatura do usuário
 *   - Expiração automática de planos vencidos
 */

import { Injectable } from '@nestjs/common';
import { SubscriptionPlan } from '@prisma/client';
import { PrismaService } from '../prisma/prisma.service';
import { getPlan, PLANS, PlanConfig } from './plans.config';

@Injectable()
export class PlansService {
  constructor(private prisma: PrismaService) {}

  /**
   * Retorna o plano ativo do usuário, considerando expiração.
   */
  async getUserPlan(userId: string): Promise<PlanConfig> {
    const subscription = await this.prisma.subscription.findFirst({
      where: { userId, status: 'active' },
      orderBy: { createdAt: 'desc' },
    });

    if (!subscription) return getPlan('free');

    // Verifica expiração
    if (subscription.expiresAt && subscription.expiresAt < new Date()) {
      await this.prisma.subscription.update({
        where: { id: subscription.id },
        data: { status: 'expired' },
      });
      return getPlan('free');
    }

    return getPlan(subscription.plan);
  }

  /**
   * Verifica se o usuário pode adicionar mais um produto.
   * @returns { allowed, reason }
   */
  async canAddProduct(userId: string): Promise<{ allowed: boolean; reason: string }> {
    const plan = await this.getUserPlan(userId);
    const count = await this.prisma.product.count({
      where: {
        alerts: { some: { userId, active: true } },
        deletedAt: null,
      },
    });

    if (count >= plan.maxProducts) {
      return {
        allowed: false,
        reason: `Limite de ${plan.maxProducts} produto(s) atingido no plano ${plan.name}. Faça upgrade para monitorar mais.`,
      };
    }

    return { allowed: true, reason: '' };
  }

  /**
   * Retorna o status completo da assinatura do usuário (para o frontend).
   */
  async getSubscriptionStatus(userId: string) {
    const plan = await this.getUserPlan(userId);
    const subscription = await this.prisma.subscription.findFirst({
      where: { userId, status: 'active' },
      orderBy: { createdAt: 'desc' },
    });

    const isPremium = plan.id !== 'free';
    const expiresAt = subscription?.expiresAt ?? null;
    const daysRemaining = expiresAt
      ? Math.max(0, Math.ceil((expiresAt.getTime() - Date.now()) / 86_400_000))
      : null;

    return {
      currentPlan: plan.id,
      planName: plan.name,
      isPremium,
      expiresAt,
      daysRemaining,
      limits: {
        maxProducts:      plan.maxProducts,
        syncPriority:     plan.syncPriority,
        priceHistoryDays: plan.priceHistoryDays,
      },
      features: {
        dealScore:         plan.dealScore,
        csvExport:         plan.csvExport,
        apiAccess:         plan.apiAccess,
        advancedAnalytics: plan.advancedAnalytics,
      },
      availablePlans: Object.values(PLANS).map((p) => ({
        id: p.id,
        name: p.name,
        priceBrl: p.priceBrl,
        priceUsd: p.priceUsd,
        description: p.description,
        highlight: p.highlight,
        badgeColor: p.badgeColor,
        badgeLabel: p.badgeLabel,
      })),
    };
  }

  /**
   * Expira assinaturas premium vencidas (executar via cron).
   * @returns Quantidade de assinaturas expiradas
   */
  async expireOverduePlans(): Promise<number> {
    const result = await this.prisma.subscription.updateMany({
      where: {
        plan: SubscriptionPlan.premium,
        status: 'active',
        expiresAt: { lt: new Date() },
      },
      data: { status: 'expired' },
    });

    return result.count;
  }
}
