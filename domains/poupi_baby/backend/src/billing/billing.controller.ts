import {
  Body,
  Controller,
  Get,
  Headers,
  Post,
  Req,
  UseGuards,
} from '@nestjs/common';

import { AuthGuard } from '@nestjs/passport';
import { BillingService } from './billing.service';

interface AuthenticatedRequest {
  user: { userId: string; email: string };
}

@Controller('billing')
export class BillingController {
  constructor(private readonly billingService: BillingService) {}

  /** Retorna o status da assinatura do usuário logado */
  @UseGuards(AuthGuard('jwt'))
  @Get('status')
  getStatus(@Req() req: AuthenticatedRequest) {
    return this.billingService.getStatus(req.user.userId);
  }

  /** Inicia um checkout para upgrade de plano */
  @UseGuards(AuthGuard('jwt'))
  @Post('checkout')
  createCheckout(
    @Req() req: AuthenticatedRequest,
    @Body('planId') planId: string,
  ) {
    return this.billingService.createCheckout(req.user.userId, planId);
  }

  /** Cancela a assinatura do usuário logado */
  @UseGuards(AuthGuard('jwt'))
  @Post('cancel')
  cancelSubscription(
    @Req() req: AuthenticatedRequest,
    @Body('subscriptionId') subscriptionId: string,
  ) {
    return this.billingService.cancelSubscription(req.user.userId, subscriptionId);
  }

  /** Webhook do MercadoPago */
  @Post('webhook/mercadopago')
  async webhookMercadoPago(
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    @Req() req: any,
    @Headers('x-signature') signature: string,
    @Body() payload: unknown,
  ) {
    const raw: Buffer = req.rawBody ?? Buffer.from(JSON.stringify(payload));
    if (!this.billingService.validateWebhook(raw, signature)) {
      return { ok: false, error: 'Assinatura inválida' };
    }
    await this.billingService.handleWebhook(payload);
    return { ok: true };
  }

  /** Webhook do Stripe */
  @Post('webhook/stripe')
  async webhookStripe(
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    @Req() req: any,
    @Headers('stripe-signature') signature: string,
    @Body() payload: unknown,
  ) {
    const raw: Buffer = req.rawBody ?? Buffer.from(JSON.stringify(payload));
    if (!this.billingService.validateWebhook(raw, signature)) {
      return { ok: false, error: 'Assinatura inválida' };
    }
    await this.billingService.handleWebhook(payload);
    return { ok: true };
  }
}
