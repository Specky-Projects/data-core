/**
 * gateway.interface.ts
 *
 * Contrato que todos os gateways de pagamento devem implementar.
 * Seguindo o princípio de substituição de Liskov (SOLID),
 * o BillingService não precisa saber qual gateway está em uso.
 *
 * Para adicionar um novo gateway:
 *   1. Crie `<nome>.gateway.ts` implementando `PaymentGateway`
 *   2. Registre no factory `getGateway()` em billing.service.ts
 */

export interface CheckoutSession {
  sessionId: string;
  checkoutUrl: string;
  expiresAt: Date;
  provider: string;
  amountBrl: number;
}

export interface PaymentEvent {
  eventId: string;
  eventType: 'payment.approved' | 'payment.cancelled' | 'payment.refunded' | 'subscription.cancelled' | string;
  userId: string;
  paymentId: string;
  amountBrl: number;
  provider: string;
  rawData: Record<string, unknown>;
}

export interface PaymentGateway {
  readonly provider: string;

  /**
   * Cria uma sessão de checkout e retorna a URL de pagamento.
   */
  createCheckout(userId: string, planId: string, amountBrl: number): Promise<CheckoutSession>;

  /**
   * Valida a assinatura do webhook recebido.
   * Deve retornar false se a assinatura for inválida (segurança).
   */
  validateWebhook(payload: Buffer | string, signature: string): boolean;

  /**
   * Parseia o payload do webhook para um PaymentEvent normalizado.
   */
  parseWebhook(payload: unknown): Promise<PaymentEvent | null>;

  /**
   * Cancela uma assinatura recorrente.
   */
  cancelSubscription(subscriptionId: string): Promise<void>;
}
