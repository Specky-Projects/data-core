/**
 * analytics-events.listener.ts
 *
 * Persiste UserEvents disparados pelo event bus.
 * Ouve `analytics.user_event` — qualquer módulo pode emitir este evento
 * para registrar comportamento sem depender diretamente do AnalyticsService.
 */

import { Injectable, Logger } from '@nestjs/common';
import { OnEvent } from '@nestjs/event-emitter';
import { AnalyticsService } from '../analytics.service';
import { DOMAIN_EVENTS } from '../../shared/events/domain-events';

@Injectable()
export class AnalyticsEventsListener {
  private readonly logger = new Logger(AnalyticsEventsListener.name);

  constructor(private readonly analytics: AnalyticsService) {}

  @OnEvent(DOMAIN_EVENTS.USER_EVENT)
  handleUserEvent(event: {
    payload: {
      userId:    string;
      sessionId?: string;
      eventType: string;
      payload?:  Record<string, unknown>;
    };
  }): void {
    // Fire-and-forget — nunca bloqueia o emissor
    this.analytics.trackAsync({
      userId:    event.payload.userId,
      sessionId: event.payload.sessionId,
      eventType: event.payload.eventType,
      payload:   event.payload.payload,
    });
  }

  /**
   * Quando um alerta é disparado, registra evento de conversão.
   * Útil para medir: quantos alertas criados → disparados.
   */
  @OnEvent(DOMAIN_EVENTS.ALERT_TRIGGERED)
  handleAlertTriggered(event: {
    payload: { alertId: string; userId: string; productId: string };
  }): void {
    const { userId, productId, alertId } = event.payload;

    this.analytics.trackAsync({
      userId,
      eventType: 'alert.triggered',
      payload:   { alertId, productId },
    });
  }

  /**
   * Quando deal score alto → registra "deal opportunity" para análise de funil.
   */
  @OnEvent(DOMAIN_EVENTS.DEAL_SCORE_HIGH)
  handleDealScoreHigh(event: {
    payload: { productId: string; offerId: string; score: number };
  }): void {
    // Sem userId aqui (evento de sistema) — registra sem associação a usuário
    this.logger.debug(
      `[analytics-listener] deal.score_high registrado — productId=${event.payload.productId} score=${event.payload.score}`,
    );
    // TODO: quando tiver userId nos alertas ativos, registrar por usuário
  }
}
