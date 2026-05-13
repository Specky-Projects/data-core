/**
 * plans.config.ts
 *
 * Fonte única da verdade para planos do Poupi.
 *
 * Para EDITAR um plano: altere aqui. Nenhum outro arquivo precisa mudar.
 * Para ADICIONAR um plano:
 *   1. Adicione a chave em PLANS abaixo
 *   2. Adicione o valor no enum SubscriptionPlan do Prisma schema
 *   3. Execute: npx prisma db push
 */

export interface PlanConfig {
  id:          string;
  name:        string;
  priceBrl:    number;        // Preço mensal em BRL
  priceUsd:    number;        // Preço mensal em USD
  description: string;

  // ── Limites operacionais ────────────────────────────────────────────────
  maxProducts:      number;   // Máximo de produtos monitorados (-1 = ilimitado)
  maxAlerts:        number;   // Máximo de alertas ativos (-1 = ilimitado)
  syncPriority:     'slow' | 'normal' | 'fast' | 'realtime';
  priceHistoryDays: number;   // Dias de histórico mantido (-1 = ilimitado)

  // ── Features ────────────────────────────────────────────────────────────
  dealScore:        boolean;  // Score inteligente de oferta
  emailAlerts:      boolean;  // Alertas por email
  csvExport:        boolean;  // Exportar histórico CSV
  apiAccess:        boolean;  // Acesso à API REST pública
  advancedAnalytics: boolean; // Analytics avançado (volatilidade, tendências)

  // ── UI ──────────────────────────────────────────────────────────────────
  badgeColor:  string;
  badgeLabel:  string;
  highlight:   boolean;       // Destaque no pricing page ("mais popular")
}

// ═══════════════════════════════════════════════════════════════════════════
// EDITE AQUI os limites e preços de cada plano
// ═══════════════════════════════════════════════════════════════════════════

export const PLANS: Record<string, PlanConfig> = {

  free: {
    id:          'free',
    name:        'Free',
    priceBrl:    0,
    priceUsd:    0,
    description: 'Para quem quer experimentar o monitoramento de preços',

    maxProducts:      10,
    maxAlerts:        1,
    syncPriority:     'slow',    // intervalo 24h
    priceHistoryDays: 7,

    dealScore:         false,
    emailAlerts:       true,
    csvExport:         false,
    apiAccess:         false,
    advancedAnalytics: false,

    badgeColor: '#4b5563',
    badgeLabel: 'Grátis',
    highlight:  false,
  },

  plus: {
    id:          'plus',
    name:        'Plus',
    priceBrl:    14.90,
    priceUsd:    2.99,
    description: 'Para quem compra online com frequência',

    maxProducts:      200,
    maxAlerts:        -1,        // ilimitado
    syncPriority:     'normal',  // intervalo 6h
    priceHistoryDays: 90,

    dealScore:         true,
    emailAlerts:       true,
    csvExport:         true,
    apiAccess:         false,
    advancedAnalytics: false,

    badgeColor: '#6C2BD9',
    badgeLabel: 'Plus',
    highlight:  true,
  },

  pro: {
    id:          'pro',
    name:        'Pro',
    priceBrl:    39.90,
    priceUsd:    7.99,
    description: 'Para power users e revendedores',

    maxProducts:      -1,        // ilimitado
    maxAlerts:        -1,        // ilimitado
    syncPriority:     'fast',    // intervalo 2h
    priceHistoryDays: -1,        // ilimitado

    dealScore:         true,
    emailAlerts:       true,
    csvExport:         true,
    apiAccess:         true,
    advancedAnalytics: true,

    badgeColor: '#f59e0b',
    badgeLabel: 'Pro',
    highlight:  false,
  },

};

// Mapeia o enum Prisma SubscriptionPlan → PlanConfig
// (premium → plus para compatibilidade com dados existentes)
const PLAN_ALIAS: Record<string, string> = {
  free:       'free',
  premium:    'plus',   // alias legado
  plus:       'plus',
  pro:        'pro',
  enterprise: 'pro',   // alias legado
};

export function getPlan(planId: string): PlanConfig {
  const key = PLAN_ALIAS[planId] ?? planId;
  return PLANS[key] ?? PLANS.free;
}

/** Retorna os limites de quota do usuário com base na subscription ativa */
export function getQuota(plan: PlanConfig) {
  return {
    maxProducts:  plan.maxProducts,
    maxAlerts:    plan.maxAlerts,
    syncPriority: plan.syncPriority,
    historyDays:  plan.priceHistoryDays,
  };
}

/** true se o limite foi atingido (-1 = ilimitado) */
export function isAtLimit(current: number, max: number): boolean {
  if (max === -1) return false;
  return current >= max;
}
