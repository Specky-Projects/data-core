/**
 * stripe.gateway.ts
 *
 * Gateway de pagamento via Stripe.
 * Suporta: Cartão de Crédito, modo subscription.
 *
 * Variáveis de ambiente necessárias:
 *   STRIPE_SECRET_KEY       — chave secreta do Stripe
 *   STRIPE_WEBHOOK_SECRET   — secret do endpoint de webhook (whsec_...)
 *   STRIPE_PRICE_ID_PREMIUM — price ID do plano premium no Stripe
 *   FRONTEND_URL            — URL pública do frontend
 */

import * as crypto from 'crypto';
import { CheckoutSession, PaymentEvent, PaymentGateway } from './gateway.interface';

export class StripeGateway implements PaymentGateway {
  readonly provider = 'stripe';

  private get secretKey(): string {
    return process.env.STRIPE_SECRET_KEY ?? '';
  }

  private get webhookSecret(): string {
    return process.env.STRIPE_WEBHOOK_SECRET ?? '';
  }

  private async stripePost(path: string, body: Record<string, string>): Promise<unknown> {
    const params = new URLSearchParams(body).toString();
    const res = await fetch(`https://api.stripe.com/v1${path}`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${this.secretKey}`,
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: params,
    });
    if (!res.ok) throw new Error(`Stripe ${path} falhou: ${res.status}`);
    return res.json();
  }

  async createCheckout(userId: string, planId: string, _amountBrl: number): Promise<CheckoutSession> {
    const frontendUrl = process.env.FRONTEND_URL || 'http://localhost:3000';
    const priceId = process.env.STRIPE_PRICE_ID_PREMIUM ?? '';

    const session = await this.stripePost('/checkout/sessions', {
      mode: 'subscription',
      'line_items[0][price]': priceId,
      'line_items[0][quantity]': '1',
      success_url: `${frontendUrl}/billing/success?session_id={CHECKOUT_SESSION_ID}`,
      cancel_url: `${frontendUrl}/billing/cancel`,
      client_reference_id: userId,
      'metadata[userId]': userId,
      'metadata[planId]': planId,
    }) as { id: string; url: string };

    return {
      sessionId: session.id,
      checkoutUrl: session.url,
      expiresAt: new Date(Date.now() + 30 * 60_000),
      provider: this.provider,
      amountBrl: _amountBrl,
    };
  }

  validateWebhook(payload: Buffer | string, signature: string): boolean {
    if (!this.webhookSecret) return true;
    try {
      // Stripe usa header Stripe-Signature com timestamp + HMAC
      const parts = signature.split(',').reduce<Record<string, string>>((acc, p) => {
        const [k, v] = p.split('=');
        acc[k] = v;
        return acc;
      }, {});

      const ts = parts['t'];
      const sig = parts['v1'];
      const signed = `${ts}.${payload.toString()}`;
      const expected = crypto
        .createHmac('sha256', this.webhookSecret)
        .update(signed)
        .digest('hex');

      return crypto.timingSafeEqual(Buffer.from(expected), Buffer.from(sig ?? ''));
    } catch { return false; }
  }

  async parseWebhook(payload: unknown): Promise<PaymentEvent | null> {
    const event = payload as { type: string; data: { object: Record<string, unknown> } };
    const obj = event?.data?.object ?? {};

    const eventTypeMap: Record<string, PaymentEvent['eventType']> = {
      'checkout.session.completed': 'payment.approved',
      'customer.subscription.deleted': 'subscription.cancelled',
      'invoice.payment_failed': 'payment.cancelled',
    };

    const eventType = eventTypeMap[event.type];
    if (!eventType) return null;

    return {
      eventId: String(obj['id'] ?? ''),
      eventType,
      userId: String(obj['client_reference_id'] ?? (obj['metadata'] as Record<string, string>)?.['userId'] ?? ''),
      paymentId: String(obj['payment_intent'] ?? obj['id'] ?? ''),
      amountBrl: Number(obj['amount_total'] ?? 0) / 100,
      provider: this.provider,
      rawData: obj,
    };
  }

  async cancelSubscription(subscriptionId: string): Promise<void> {
    await fetch(`https://api.stripe.com/v1/subscriptions/${subscriptionId}`, {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${this.secretKey}` },
    });
  }
}
