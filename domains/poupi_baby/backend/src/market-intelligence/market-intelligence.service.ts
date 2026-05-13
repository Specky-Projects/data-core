/**
 * market-intelligence.service.ts
 *
 * Calcula e persiste padrões de mercado por produto+marketplace.
 *
 * Padrões identificados:
 *   - PRICE_TREND:  direção e força da tendência de preço (30 e 90 dias)
 *   - PROMO_CYCLE:  ciclo promocional (dias médios entre promoções)
 *   - VOLATILITY:   volatilidade de preço (coeficiente de variação)
 *
 * Schema notes:
 *   - PriceHistory → Offer (offerId) → Product (productId)
 *   - PriceHistory → Offer (offerId) → Marketplace (marketplaceId)
 *   - MarketPattern.marketplace = Marketplace.name (string)
 */

import { Injectable, Logger } from '@nestjs/common';
import { PrismaService } from '../prisma/prisma.service';

export type TrendDirection = 'UP' | 'DOWN' | 'STABLE';

export interface MarketPatternResult {
  productId:            string;
  marketplace:          string;
  patternType:          string;
  trendDirection:       TrendDirection;
  trendStrength:        number;        // 0–1
  priceVolatility30d:   number | null;
  priceVolatility90d:   number | null;
  avgDaysBetweenPromos: number | null;
  nextPromoEst:         Date | null;
  monthlyAvgPrices:     Record<string, number>;
  monthlyPromoRates:    Record<string, number>;
}

interface PricePoint {
  price:      number;
  capturedAt: Date;
}

@Injectable()
export class MarketIntelligenceService {
  private readonly logger = new Logger(MarketIntelligenceService.name);

  constructor(private readonly prisma: PrismaService) {}

  // ── Análise principal ─────────────────────────────────────────────────────

  /**
   * Calcula todos os padrões para um produto+marketplace e persiste.
   * `marketplace` deve ser o Marketplace.name exato (case-insensitive).
   */
  async analyzeProduct(
    productId: string,
    marketplace: string,
  ): Promise<MarketPatternResult | null> {
    const history = await this.loadHistory(productId, marketplace, 90);

    if (history.length < 5) {
      this.logger.debug(
        `[market] Dados insuficientes para ${marketplace}/${productId} (${history.length} pontos)`,
      );
      return null;
    }

    const prices = history.map((h) => h.price);

    const vol30  = this.volatility(prices.slice(-30));
    const vol90  = this.volatility(prices);
    const trend  = this.calcTrend(prices);
    const monthly = this.calcMonthlyAverages(history);

    const result: MarketPatternResult = {
      productId,
      marketplace,
      patternType:          'PRICE_TREND',
      trendDirection:       trend.direction,
      trendStrength:        trend.strength,
      priceVolatility30d:   vol30,
      priceVolatility90d:   vol90,
      avgDaysBetweenPromos: null,   // expandir quando tiver dados de promoção
      nextPromoEst:         null,
      monthlyAvgPrices:     monthly.avgPrices,
      monthlyPromoRates:    monthly.promoRates,
    };

    await this.persist(result);
    return result;
  }

  /**
   * Analisa todas as combinações produto+marketplace com scraping recente.
   * Chamado pelo scheduler.
   */
  async analyzeRecent(hoursBack = 24): Promise<number> {
    const since = new Date(Date.now() - hoursBack * 60 * 60 * 1000);

    // Ofertas com price history recente (produto+marketplace únicos)
    const recentOffers = await this.prisma.offer.findMany({
      where: {
        deletedAt: null,
        priceHistory: { some: { capturedAt: { gte: since } } },
      },
      select: {
        productId:   true,
        marketplace: { select: { name: true } },
      },
      distinct: ['productId', 'marketplaceId'],
    });

    let analyzed = 0;
    for (const offer of recentOffers) {
      const mpName = offer.marketplace.name;
      try {
        const result = await this.analyzeProduct(offer.productId, mpName);
        if (result) analyzed++;
      } catch (err) {
        this.logger.error(
          `[market] Erro ao analisar ${mpName}/${offer.productId}: ${err?.message}`,
        );
      }
    }

    this.logger.log(
      `[market] Análise concluída: ${analyzed}/${recentOffers.length} produtos processados`,
    );
    return analyzed;
  }

  // ── Consultas ─────────────────────────────────────────────────────────────

  async getPattern(productId: string, marketplace: string) {
    return this.prisma.marketPattern.findUnique({
      where: {
        productId_marketplace_patternType: {
          productId,
          marketplace,
          patternType: 'PRICE_TREND',
        },
      },
    });
  }

  async getAllPatterns(productId: string) {
    return this.prisma.marketPattern.findMany({
      where:   { productId },
      orderBy: { computedAt: 'desc' },
    });
  }

  /**
   * Produtos com tendência de queda de preço (oportunidades de compra).
   */
  async getDownwardTrends(minStrength = 0.3, limit = 50) {
    const rows = await this.prisma.marketPattern.findMany({
      where: {
        trendDirection: 'DOWN',
        trendStrength:  { gte: minStrength },
      },
      orderBy: { trendStrength: 'desc' },
      take:    limit,
      include: {
        product: { select: { id: true, title: true, slug: true } },
      },
    });

    return rows.map((r) => ({
      productId:     r.productId,
      productTitle:  r.product.title,
      productSlug:   r.product.slug,
      marketplace:   r.marketplace,
      trendStrength: r.trendStrength,
      volatility30d: r.priceVolatility30d,
      nextPromoEst:  r.nextPromoEst,
      computedAt:    r.computedAt,
    }));
  }

  /**
   * Produtos com promoção estimada nas próximas N horas.
   */
  async getUpcomingPromos(withinHours = 72, limit = 50) {
    const upperBound = new Date(Date.now() + withinHours * 60 * 60 * 1000);

    const rows = await this.prisma.marketPattern.findMany({
      where: {
        nextPromoEst: { lte: upperBound, gte: new Date() },
      },
      orderBy: { nextPromoEst: 'asc' },
      take:    limit,
      include: {
        product: { select: { id: true, title: true, slug: true } },
      },
    });

    return rows.map((r) => ({
      productId:            r.productId,
      productTitle:         r.product.title,
      marketplace:          r.marketplace,
      nextPromoEst:         r.nextPromoEst,
      avgDaysBetweenPromos: r.avgDaysBetweenPromos,
    }));
  }

  // ── Cálculos ──────────────────────────────────────────────────────────────

  private calcTrend(prices: number[]): { direction: TrendDirection; strength: number } {
    if (prices.length < 2) return { direction: 'STABLE', strength: 0 };

    // Regressão linear simples
    const n     = prices.length;
    const xMean = (n - 1) / 2;
    const yMean = prices.reduce((s, p) => s + p, 0) / n;

    let num = 0;
    let den = 0;
    for (let i = 0; i < n; i++) {
      num += (i - xMean) * (prices[i] - yMean);
      den += (i - xMean) ** 2;
    }

    const slope         = den === 0 ? 0 : num / den;
    const relativeSlope = yMean === 0 ? 0 : slope / yMean;

    // ±0.5% por ponto = sinal claro de tendência
    const THRESHOLD = 0.005;
    let direction: TrendDirection = 'STABLE';
    if (relativeSlope > THRESHOLD)  direction = 'UP';
    if (relativeSlope < -THRESHOLD) direction = 'DOWN';

    // Força normalizada, caps em 1
    const strength = Math.min(1, Math.abs(relativeSlope) / (THRESHOLD * 10));
    return { direction, strength: Math.round(strength * 1000) / 1000 };
  }

  private volatility(prices: number[]): number | null {
    if (prices.length < 3) return null;
    const mean = prices.reduce((s, p) => s + p, 0) / prices.length;
    if (mean === 0) return null;
    const variance = prices.reduce((s, p) => s + (p - mean) ** 2, 0) / prices.length;
    const std      = Math.sqrt(variance);
    // Coeficiente de variação em %
    return Math.round((std / mean) * 10000) / 100;
  }

  private calcMonthlyAverages(history: PricePoint[]): {
    avgPrices:  Record<string, number>;
    promoRates: Record<string, number>;
  } {
    const byMonth = new Map<string, { sum: number; count: number }>();

    for (const h of history) {
      const key   = h.capturedAt.toISOString().slice(0, 7); // YYYY-MM
      const entry = byMonth.get(key) ?? { sum: 0, count: 0 };
      entry.sum  += h.price;
      entry.count++;
      byMonth.set(key, entry);
    }

    const avgPrices:  Record<string, number> = {};
    const promoRates: Record<string, number> = {};

    for (const [month, { sum, count }] of byMonth) {
      avgPrices[month]  = Math.round((sum / count) * 100) / 100;
      promoRates[month] = 0; // placeholder — preencher com dados de promoção futuramente
    }

    return { avgPrices, promoRates };
  }

  // ── Persistência ──────────────────────────────────────────────────────────

  private async persist(result: MarketPatternResult): Promise<void> {
    const {
      productId, marketplace, patternType,
      trendDirection, trendStrength,
      priceVolatility30d, priceVolatility90d,
      avgDaysBetweenPromos, nextPromoEst,
      monthlyAvgPrices, monthlyPromoRates,
    } = result;

    const data = {
      trendDirection,
      trendStrength,
      priceVolatility30d:   priceVolatility30d  ?? undefined,
      priceVolatility90d:   priceVolatility90d  ?? undefined,
      avgDaysBetweenPromos: avgDaysBetweenPromos ?? undefined,
      nextPromoEst:         nextPromoEst         ?? undefined,
      monthlyAvgPrices:     JSON.stringify(monthlyAvgPrices),
      monthlyPromoRates:    JSON.stringify(monthlyPromoRates),
      computedAt:           new Date(),
    };

    await this.prisma.marketPattern.upsert({
      where:  { productId_marketplace_patternType: { productId, marketplace, patternType } },
      update: data,
      create: { productId, marketplace, patternType, ...data },
    });
  }

  // ── Data loading ──────────────────────────────────────────────────────────

  /**
   * Carrega histórico de preços de um produto para um marketplace específico.
   * Rota: Offer.productId + Offer.marketplace.name → PriceHistory
   */
  private async loadHistory(
    productId: string,
    marketplace: string,
    days: number,
  ): Promise<PricePoint[]> {
    const since = new Date();
    since.setDate(since.getDate() - days);

    // Encontra ofertas do produto neste marketplace
    const offers = await this.prisma.offer.findMany({
      where: {
        productId,
        deletedAt: null,
        marketplace: { name: { equals: marketplace, mode: 'insensitive' } },
      },
      select: { id: true },
    });

    if (offers.length === 0) return [];

    const offerIds = offers.map((o) => o.id);

    const rows = await this.prisma.priceHistory.findMany({
      where:   { offerId: { in: offerIds }, capturedAt: { gte: since } },
      orderBy: { capturedAt: 'asc' },
      select:  { price: true, capturedAt: true },
    });

    return rows.map((r) => ({
      price:      Number(r.price),
      capturedAt: r.capturedAt,
    }));
  }
}
