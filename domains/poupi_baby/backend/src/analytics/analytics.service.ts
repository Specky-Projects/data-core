/**
 * analytics.service.ts
 *
 * Persiste e consulta eventos de comportamento do usuário (UserEvent).
 *
 * Eventos rastreados:
 *   product.viewed         — usuário visualizou página de produto
 *   alert.created          — usuário criou alerta de preço
 *   alert.deleted          — usuário deletou alerta
 *   deal.clicked           — usuário clicou em "ir para oferta" (afiliado)
 *   price_history.viewed   — usuário expandiu gráfico de histórico
 *   billing.checkout_started — usuário iniciou checkout de plano
 *   search.performed       — usuário fez busca no catálogo
 *
 * Todos os payloads são armazenados como JSON em `payload` (Text).
 * PII: userId é incluído — tratar com LGPD em mente.
 */

import { Injectable, Logger } from '@nestjs/common';
import { PrismaService } from '../prisma/prisma.service';

export type EventType =
  | 'product.viewed'
  | 'alert.created'
  | 'alert.deleted'
  | 'deal.clicked'
  | 'price_history.viewed'
  | 'billing.checkout_started'
  | 'search.performed'
  | string; // extensível

export interface TrackEventInput {
  userId:     string;
  sessionId?: string;
  eventType:  EventType;
  payload?:   Record<string, unknown>;
}

export interface FunnelStep {
  step:    EventType;
  count:   number;
  dropOff: number; // % que não chegou ao próximo step
}

@Injectable()
export class AnalyticsService {
  private readonly logger = new Logger(AnalyticsService.name);

  constructor(private readonly prisma: PrismaService) {}

  // ── Track ─────────────────────────────────────────────────────────────────

  async track(input: TrackEventInput): Promise<void> {
    try {
      await this.prisma.userEvent.create({
        data: {
          userId:    input.userId,
          sessionId: input.sessionId ?? null,
          eventType: input.eventType,
          payload:   JSON.stringify(input.payload ?? {}),
        },
      });
    } catch (err: any) {
      // Nunca propaga erro — analytics não pode derrubar o fluxo principal
      this.logger.error(`[analytics] Falha ao gravar evento: ${err.message}`);
    }
  }

  /** Versão fire-and-forget para uso em handlers de evento */
  trackAsync(input: TrackEventInput): void {
    this.track(input).catch(() => {}); // erro já logado em track()
  }

  // ── Consultas ─────────────────────────────────────────────────────────────

  /**
   * Eventos de um usuário — para auditoria / suporte.
   */
  async getUserEvents(
    userId: string,
    opts: { limit?: number; eventType?: string; since?: Date } = {},
  ) {
    const { limit = 100, eventType, since } = opts;

    const rows = await this.prisma.userEvent.findMany({
      where: {
        userId,
        ...(eventType ? { eventType } : {}),
        ...(since ? { occurredAt: { gte: since } } : {}),
      },
      orderBy: { occurredAt: 'desc' },
      take:    limit,
    });

    return rows.map((r) => ({
      ...r,
      payload: this.parseJson(r.payload, {}),
    }));
  }

  /**
   * Contagem de eventos por tipo nos últimos N dias — para dashboard de admin.
   */
  async getEventCounts(days = 7): Promise<Array<{ eventType: string; count: number }>> {
    const since = new Date();
    since.setDate(since.getDate() - days);

    const rows = await this.prisma.userEvent.groupBy({
      by:      ['eventType'],
      where:   { occurredAt: { gte: since } },
      _count:  { _all: true },
      orderBy: { _count: { eventType: 'desc' } },
    });

    return rows.map((r) => ({
      eventType: r.eventType,
      count:     r._count._all,
    }));
  }

  /**
   * Usuários únicos ativos nos últimos N dias.
   */
  async getActiveUsers(days = 30): Promise<number> {
    const since = new Date();
    since.setDate(since.getDate() - days);

    const result = await this.prisma.userEvent.findMany({
      where:    { occurredAt: { gte: since } },
      distinct: ['userId'],
      select:   { userId: true },
    });

    return result.length;
  }

  /**
   * Produtos mais visualizados nos últimos N dias.
   */
  async getTopProducts(days = 7, limit = 20): Promise<Array<{ productId: string; views: number }>> {
    const since = new Date();
    since.setDate(since.getDate() - days);

    const rows = await this.prisma.userEvent.findMany({
      where: {
        eventType:  'product.viewed',
        occurredAt: { gte: since },
      },
      select: { payload: true },
    });

    // Conta por productId dentro do payload JSON
    const counts: Record<string, number> = {};
    for (const row of rows) {
      const p = this.parseJson<{ productId?: string }>(row.payload, {});
      if (p.productId) counts[p.productId] = (counts[p.productId] ?? 0) + 1;
    }

    return Object.entries(counts)
      .map(([productId, views]) => ({ productId, views }))
      .sort((a, b) => b.views - a.views)
      .slice(0, limit);
  }

  /**
   * Funil de conversão — de view ao clique de afiliado.
   */
  async getConversionFunnel(days = 30): Promise<FunnelStep[]> {
    const since = new Date();
    since.setDate(since.getDate() - days);

    const steps: EventType[] = [
      'product.viewed',
      'price_history.viewed',
      'alert.created',
      'deal.clicked',
    ];

    const counts = await Promise.all(
      steps.map((eventType) =>
        this.prisma.userEvent.count({
          where: { eventType, occurredAt: { gte: since } },
        }),
      ),
    );

    return steps.map((step, i) => ({
      step,
      count:   counts[i],
      dropOff: i === 0 || counts[i - 1] === 0
        ? 0
        : Math.round(((counts[i - 1] - counts[i]) / counts[i - 1]) * 100),
    }));
  }

  /**
   * Série temporal de eventos por dia — para gráfico no dashboard admin.
   */
  async getTimeSeries(
    eventType: string,
    days = 30,
  ): Promise<Array<{ date: string; count: number }>> {
    const since = new Date();
    since.setDate(since.getDate() - days);

    const rows = await this.prisma.userEvent.findMany({
      where:   { eventType, occurredAt: { gte: since } },
      select:  { occurredAt: true },
      orderBy: { occurredAt: 'asc' },
    });

    const byDay = new Map<string, number>();
    for (const row of rows) {
      const day = row.occurredAt.toISOString().slice(0, 10);
      byDay.set(day, (byDay.get(day) ?? 0) + 1);
    }

    return Array.from(byDay.entries()).map(([date, count]) => ({ date, count }));
  }

  // ── Helpers ───────────────────────────────────────────────────────────────

  private parseJson<T>(str: string | null, fallback: T): T {
    if (!str) return fallback;
    try { return JSON.parse(str); } catch { return fallback; }
  }
}
