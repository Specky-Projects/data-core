/**
 * deal-score.service.ts
 *
 * Motor de inteligência de compra — calcula um score 0–100 para cada oferta.
 *
 * Componentes do score (pesos):
 *
 *   A. Desconto histórico (30pts)
 *      Quanto o preço atual caiu em relação à média dos últimos 90 dias.
 *      Desconto >= 30% → 30pts; proporcional abaixo.
 *
 *   B. Proximidade do menor preço histórico (25pts)
 *      Quanto mais próximo do all-time low, maior a pontuação.
 *      Igual ao menor → 25pts; proporcional.
 *
 *   C. Baixa volatilidade (20pts)
 *      Preço estável = você não está vendo uma oscilação casual.
 *      Coeficiente de variação baixo → mais pts.
 *
 *   D. Tendência de queda recente (15pts)
 *      Se o preço caiu nos últimos 7 dias, é um sinal positivo.
 *
 *   E. Frequência promocional (10pts)
 *      Produto que raramente está em promoção → quando cai, vale mais.
 *      Produto que sempre oscila → menos significativo.
 *
 * Classificação:
 *   90–100  → Oferta do século (raridade absoluta)
 *   75–89   → Ótima oferta
 *   60–74   → Boa oferta
 *   40–59   → Preço razoável
 *   < 40    → Preço normal / caro
 */

import { Injectable } from '@nestjs/common';
import { PrismaService } from '../prisma/prisma.service';

export interface DealScore {
  score:            number;          // 0–100
  label:            string;          // "Ótima oferta", "Preço normal"...
  labelColor:       string;          // cor hex
  emoji:            string;          // emoji para UI

  // Componentes individuais (para transparência / tooltip)
  components: {
    historicalDiscount: number;      // 0–30
    nearAllTimeLow:     number;      // 0–25
    stability:          number;      // 0–20
    recentTrend:        number;      // 0–15
    promoRarity:        number;      // 0–10
  };

  // Contexto que fundamenta o score
  context: {
    currentPrice:     number;
    avg90d:           number | null;
    minPrice90d:      number | null;
    allTimeMin:       number | null;
    discountVsAvg:    number | null;  // % de desconto vs média
    discountVsMin:    number | null;  // % acima do menor preço
    pricePoints:      number;         // quantos pontos de dados
    daysMonitored:    number;
  };
}

// ── Labels ────────────────────────────────────────────────────────────────────

function classify(score: number): { label: string; color: string; emoji: string } {
  if (score >= 90) return { label: 'Oferta do século',  color: '#22c55e', emoji: '🔥' };
  if (score >= 75) return { label: 'Ótima oferta',      color: '#4ade80', emoji: '⚡' };
  if (score >= 60) return { label: 'Boa oferta',        color: '#86efac', emoji: '✅' };
  if (score >= 40) return { label: 'Preço razoável',    color: '#fbbf24', emoji: '👍' };
  return                  { label: 'Preço normal',      color: '#94a3b8', emoji: '😐' };
}

// ── Cálculo ───────────────────────────────────────────────────────────────────

function clamp(v: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, v));
}

function stdDev(values: number[]): number {
  if (values.length < 2) return 0;
  const avg = values.reduce((a, b) => a + b, 0) / values.length;
  const variance = values.reduce((s, v) => s + (v - avg) ** 2, 0) / values.length;
  return Math.sqrt(variance);
}

@Injectable()
export class DealScoreService {
  constructor(private readonly prisma: PrismaService) {}

  /**
   * Calcula o deal score para uma oferta específica.
   * Retorna null se não houver histórico suficiente (< 3 pontos).
   */
  async calculate(offerId: string): Promise<DealScore | null> {
    const history = await this.prisma.priceHistory.findMany({
      where:   { offerId },
      orderBy: { capturedAt: 'asc' },
      select:  { price: true, capturedAt: true },
    });

    if (history.length < 3) return null;

    const offer = await this.prisma.offer.findUnique({
      where:  { id: offerId },
      select: { price: true },
    });
    if (!offer) return null;

    const currentPrice = Number(offer.price);
    const prices       = history.map((h) => Number(h.price));
    const now          = Date.now();

    // Janelas temporais
    const days90  = now - 90  * 86_400_000;
    const days7   = now - 7   * 86_400_000;
    const days30  = now - 30  * 86_400_000;

    const prices90d = history.filter((h) => h.capturedAt.getTime() >= days90).map((h) => Number(h.price));
    const prices7d  = history.filter((h) => h.capturedAt.getTime() >= days7).map((h) => Number(h.price));

    const avg90d    = prices90d.length >= 2 ? prices90d.reduce((a, b) => a + b, 0) / prices90d.length : null;
    const min90d    = prices90d.length >= 1 ? Math.min(...prices90d) : null;
    const allTimeMin = Math.min(...prices);

    const firstDate = history[0].capturedAt;
    const daysMonitored = Math.ceil((now - firstDate.getTime()) / 86_400_000);

    // ── A. Desconto histórico (0–30) ──────────────────────────────────────
    let scoreA = 0;
    let discountVsAvg: number | null = null;
    if (avg90d && avg90d > 0) {
      discountVsAvg = ((avg90d - currentPrice) / avg90d) * 100;
      // 30% de desconto → 30pts, proporcional; preço maior que média → 0
      scoreA = clamp((discountVsAvg / 30) * 30, 0, 30);
    }

    // ── B. Proximidade do all-time low (0–25) ─────────────────────────────
    let scoreB = 0;
    let discountVsMin: number | null = null;
    if (allTimeMin > 0) {
      discountVsMin = ((currentPrice - allTimeMin) / allTimeMin) * 100;
      // 0% acima do mínimo → 25pts; 50% acima → 0pts
      scoreB = clamp(((50 - discountVsMin) / 50) * 25, 0, 25);
    }

    // ── C. Estabilidade (0–20) ────────────────────────────────────────────
    const prices30d = history.filter((h) => h.capturedAt.getTime() >= days30).map((h) => Number(h.price));
    let scoreC = 10; // default médio se não há dados
    if (prices30d.length >= 3) {
      const avg30 = prices30d.reduce((a, b) => a + b, 0) / prices30d.length;
      const cv    = avg30 > 0 ? (stdDev(prices30d) / avg30) * 100 : 0; // coef. de variação em %
      // CV < 2% → 20pts (muito estável); CV > 20% → 0pts (muito volátil)
      scoreC = clamp(((20 - cv) / 20) * 20, 0, 20);
    }

    // ── D. Tendência recente de queda (0–15) ──────────────────────────────
    let scoreD = 0;
    if (prices7d.length >= 2) {
      const first7 = prices7d[0];
      const last7  = prices7d[prices7d.length - 1];
      if (first7 > 0) {
        const change7d = ((first7 - last7) / first7) * 100; // positivo = queda
        scoreD = clamp((change7d / 10) * 15, 0, 15); // queda de 10% → 15pts
      }
    }

    // ── E. Raridade promocional (0–10) ───────────────────────────────────
    // Conta quantas vezes o preço foi <= avg * 0.9 (desconto >= 10%)
    let scoreE = 10; // default: produto novo, raridade incerta
    if (avg90d && prices90d.length >= 5) {
      const threshold     = avg90d * 0.9;
      const promoCount    = prices90d.filter((p) => p <= threshold).length;
      const promoRate     = promoCount / prices90d.length; // 0–1
      // Taxa de 0–5% → 10pts (raro); taxa > 50% → 0pts (sempre em promoção)
      scoreE = clamp(((0.5 - promoRate) / 0.5) * 10, 0, 10);
    }

    const raw   = scoreA + scoreB + scoreC + scoreD + scoreE;
    const score = Math.round(clamp(raw, 0, 100));
    const { label, color, emoji } = classify(score);

    return {
      score,
      label,
      labelColor: color,
      emoji,
      components: {
        historicalDiscount: Math.round(scoreA),
        nearAllTimeLow:     Math.round(scoreB),
        stability:          Math.round(scoreC),
        recentTrend:        Math.round(scoreD),
        promoRarity:        Math.round(scoreE),
      },
      context: {
        currentPrice,
        avg90d:         avg90d    ? Math.round(avg90d    * 100) / 100 : null,
        minPrice90d:    min90d    ? Math.round(min90d    * 100) / 100 : null,
        allTimeMin:     Math.round(allTimeMin * 100) / 100,
        discountVsAvg:  discountVsAvg !== null ? Math.round(discountVsAvg * 10) / 10 : null,
        discountVsMin:  discountVsMin !== null ? Math.round(discountVsMin * 10) / 10 : null,
        pricePoints:    history.length,
        daysMonitored,
      },
    };
  }

  /**
   * Calcula scores para todas as ofertas de um produto.
   * Retorna a melhor oferta com score mais alto.
   */
  async calculateForProduct(productId: string): Promise<{
    best: { offerId: string; marketplace: string; score: DealScore } | null;
    all:  Array<{ offerId: string; marketplace: string; score: DealScore | null }>;
  }> {
    const offers = await this.prisma.offer.findMany({
      where:   { productId, deletedAt: null },
      include: { marketplace: { select: { name: true } } },
    });

    const results = await Promise.all(
      offers.map(async (o) => ({
        offerId:     o.id,
        marketplace: o.marketplace.name,
        score:       await this.calculate(o.id),
      })),
    );

    const withScore = results.filter((r) => r.score !== null) as Array<{
      offerId: string;
      marketplace: string;
      score: DealScore;
    }>;

    const best = withScore.length
      ? withScore.reduce((a, b) => (a.score.score >= b.score.score ? a : b))
      : null;

    return { best, all: results };
  }
}
