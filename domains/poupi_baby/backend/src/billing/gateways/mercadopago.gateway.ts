/**
 * mercadopago.gateway.ts
 *
 * Gateway de pagamento via Mercado Pago.
 * Suporta: Pix, Cartão de Crédito, Boleto.
 *
 * Variáveis de ambiente necessárias:
 *   MP_ACCESS_TOKEN   — access token da conta MP
 *   MP_WEBHOOK_SECRET — secret para validação HMAC dos webhooks
 *   BACKEND_URL       — URL pública do backend (para callback URLs)
 */

import * as crypto from 'crypto';
import { CheckoutSession, PaymentEvent, PaymentGateway } from './gateway.interface';

export class MercadoPagoGateway implements PaymentGateway {
  readonly provider = 'mercadopago';

  private get accessToken(): string {
    return process.env.MP_ACCESS_TOKEN ?? '';
  }

  private get webhookSecret(): string {
    return process.env.MP_WEBHOOK_SECRET ?? '';
  }

  async createCheckout(userId: string, planId: string, amountBrl: number): Promise<CheckoutSession> {
    const backendUrl = process.env.BACKEND_URL || 'http://localhost:3001';
    const frontendUrl = process.env.FRONTEND_URL || 'http://localhost:3000';
    const expiresAt = new Date(Date.now() + 24 * 3_600_000);

    const body = {
      items: [
        {
          id: planId,
          title: `Poupi ${planId.charAt(0).toUpperCase() + planId.slice(1)}`,
          quantity: 1,
          unit_price: amountBrl,
          currency_id: 'BRL',
        },
      ],
      payer: { email: '' },
      back_urls: {
        success: `${frontendUrl}/billing/success`,
        failure: `${frontendUrl}/billing/failure`,
        pending: `${frontendUrl}/billing/pending`,
      },
      auto_return: 'approved',
      external_reference: userId,
      expiration_date_to: expiresAt.toISOString(),
      notification_url: `${backendUrl}/billing/webhook/mercadopago`,
    };

    const res = await fetch('https://api.mercadopago.com/checkout/preferences', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${this.accessToken}`,
      },
      body: JSON.stringify(body),
    });

    if (!res.ok) throw new Error(`MercadoPago createCheckout falhou: ${res.status}`);

    const data = await res.json() as { id: string; init_point: string };
    return {
      sessionId: data.id,
      checkoutUrl: data.init_point,
      expiresAt,
      provider: this.provider,
      amountBrl,
    };
  }

  validateWebhook(payload: Buffer | string, signature: string): boolean {
    if (!this.webhookSecret) return true; // sem secret configurado, aceita tudo em dev
    const hmac = crypto
      .createHmac('sha256', this.webhookSecret)
      .update(payload)
      .digest('hex');
    return crypto.timingSafeEqual(Buffer.from(hmac), Buffer.from(signature));
  }

  async parseWebhook(payload: unknown): Promise<PaymentEvent | null> {
    const data = payload as Record<string, unknown>;
    const type = data?.type as string;
    const id = (data?.data as Record<string, unknown>)?.id as string;

    if (!id || type !== 'payment') return null;

    const res = await fetch(`https://api.mercadopago.com/v1/payments/${id}`, {
      headers: { Authorization: `Bearer ${this.accessToken}` },
    });

    if (!res.ok) return null;

    const payment = await res.json() as Record<string, unknown>;
    const statusMap: Record<string, PaymentEvent['eventType']> = {
      approved: 'payment.approved',
      cancelled: 'payment.cancelled',
      refunded: 'payment.refunded',
    };

    return {
      eventId: String(id),
      eventType: statusMap[payment.status as string] ?? String(payment.status),
      userId: String(payment.external_reference ?? ''),
      paymentId: String(id),
      amountBrl: Number(payment.transaction_amount ?? 0),
      provider: this.provider,
      rawData: payment,
    };
  }

  async cancelSubscription(subscriptionId: string): Promise<void> {
    await fetch(`https://api.mercadopago.com/preapproval/${subscriptionId}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${this.accessToken}`,
      },
      body: JSON.stringify({ status: 'cancelled' }),
    });
  }
}
