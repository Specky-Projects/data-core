/**
 * mock.gateway.ts
 *
 * Gateway de pagamento para desenvolvimento e testes.
 * Simula um checkout aprovado sem integração real.
 * Ativado automaticamente quando MP_ACCESS_TOKEN e STRIPE_SECRET_KEY não estão configurados.
 */

import { CheckoutSession, PaymentEvent, PaymentGateway } from './gateway.interface';

export class MockGateway implements PaymentGateway {
  readonly provider = 'mock';

  async createCheckout(userId: string, planId: string, amountBrl: number): Promise<CheckoutSession> {
    const sessionId = `mock_${Date.now()}_${userId}`;
    const frontendUrl = process.env.FRONTEND_URL || 'http://localhost:3000';

    return {
      sessionId,
      checkoutUrl: `${frontendUrl}/billing/mock-checkout?session_id=${sessionId}&plan=${planId}`,
      expiresAt: new Date(Date.now() + 30 * 60_000),
      provider: this.provider,
      amountBrl,
    };
  }

  validateWebhook(_payload: Buffer | string, _signature: string): boolean {
    return true; // sempre válido em mock
  }

  async parseWebhook(payload: unknown): Promise<PaymentEvent | null> {
    const data = payload as Record<string, unknown>;
    return {
      eventId: `mock_${Date.now()}`,
      eventType: 'payment.approved',
      userId: String(data?.userId ?? ''),
      paymentId: `mock_pay_${Date.now()}`,
      amountBrl: Number(data?.amountBrl ?? 0),
      provider: this.provider,
      rawData: data,
    };
  }

  async cancelSubscription(_subscriptionId: string): Promise<void> {
    // no-op em mock
  }
}
