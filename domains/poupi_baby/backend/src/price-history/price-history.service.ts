import { Injectable } from '@nestjs/common';
import { PrismaService } from '../prisma/prisma.service';
import { CreatePriceHistoryDto } from './dto/create-price-history.dto';

const DEFAULT_LIMIT = 200;

@Injectable()
export class PriceHistoryService {
  constructor(private prisma: PrismaService) {}

  // ── Criação ───────────────────────────────────────────────────────────────

  async create(data: CreatePriceHistoryDto) {
    return this.prisma.priceHistory.create({
      data: { price: data.price, offer: { connect: { id: data.offerId } } },
      include: { offer: true },
    });
  }

  // ── Consultas por oferta ──────────────────────────────────────────────────

  async findByOffer(offerId: string, limit = DEFAULT_LIMIT, skip = 0) {
    return this.prisma.priceHistory.findMany({
      where: { offerId },
      orderBy: { capturedAt: 'desc' },
      take: limit,
      skip,
    });
  }

  /**
   * Estatísticas consolidadas de uma oferta:
   * mínimo, máximo, média e variação vs. preço atual.
   */
  async getSummary(offerId: string) {
    const [agg, offer, latest] = await Promise.all([
      this.prisma.priceHistory.aggregate({
        where: { offerId },
        _min: { price: true },
        _max: { price: true },
        _avg: { price: true },
        _count: { _all: true },
      }),
      this.prisma.offer.findUnique({ where: { id: offerId } }),
      this.prisma.priceHistory.findFirst({
        where: { offerId },
        orderBy: { capturedAt: 'desc' },
      }),
    ]);

    const min = Number(agg._min.price ?? 0);
    const max = Number(agg._max.price ?? 0);
    const avg = Number(agg._avg.price ?? 0);
    const current = Number(offer?.price ?? 0);
    const previous = latest ? Number(latest.price) : null;

    const changePercent =
      previous && previous !== current
        ? Math.round(((current - previous) / previous) * 1000) / 10
        : 0;

    return {
      offerId,
      current,
      min,
      max,
      avg: Math.round(avg * 100) / 100,
      records: agg._count._all,
      changePercent,      // negativo = baixou, positivo = subiu
      atHistoricalLow: current === min && min > 0,
    };
  }

  // ── Consultas por produto ─────────────────────────────────────────────────

  /**
   * Histórico de preço de um produto — agrega todas as ofertas,
   * retornando o menor preço por ponto no tempo.
   *
   * @param productId  ID do produto
   * @param days       Janela em dias (padrão: 90)
   */
  async findByProduct(productId: string, days = 90) {
    const since = new Date();
    since.setDate(since.getDate() - days);

    const rows = await this.prisma.priceHistory.findMany({
      where: {
        capturedAt: { gte: since },
        offer: { productId },
      },
      orderBy: { capturedAt: 'asc' },
      select: { price: true, capturedAt: true, offerId: true },
    });

    // Agrupa por dia, mantém o menor preço de cada dia
    const byDay = new Map<string, { price: number; capturedAt: Date }>();
    for (const row of rows) {
      const day = row.capturedAt.toISOString().slice(0, 10); // YYYY-MM-DD
      const price = Number(row.price);
      const existing = byDay.get(day);
      if (!existing || price < existing.price) {
        byDay.set(day, { price, capturedAt: row.capturedAt });
      }
    }

    return Array.from(byDay.values()).sort(
      (a, b) => a.capturedAt.getTime() - b.capturedAt.getTime(),
    );
  }

  /**
   * Resumo consolidado para um produto (todos as suas ofertas).
   */
  async getProductSummary(productId: string) {
    const offers = await this.prisma.offer.findMany({
      where: { productId, deletedAt: null },
      include: {
        marketplace: { select: { name: true } },
        _count: { select: { priceHistory: true } },
      },
    });

    const summaries = await Promise.all(
      offers.map(async (o) => ({
        ...(await this.getSummary(o.id)),
        marketplace: o.marketplace.name,
        productUrl: o.productUrl,
      })),
    );

    // Menor preço atual entre todas as ofertas
    const bestOffer = summaries.reduce(
      (best, s) => (s.current < best.current ? s : best),
      summaries[0],
    );

    return { productId, bestOffer, offers: summaries };
  }

  // ── Admin ─────────────────────────────────────────────────────────────────

  async findAll(limit = DEFAULT_LIMIT, skip = 0) {
    return this.prisma.priceHistory.findMany({
      include: { offer: true },
      orderBy: { capturedAt: 'desc' },
      take: limit,
      skip,
    });
  }
}
