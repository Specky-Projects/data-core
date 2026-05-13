import { Injectable, Logger } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { PrismaService } from '../prisma/prisma.service';
import { EventBusService } from '../shared/events/event-bus.service';
import { DOMAIN_EVENTS } from '../shared/events/domain-events';
import {
  extractKeywordSignals,
  aggregateKeywordSignals,
  KeywordCategory,
} from './config/review-keywords';
import {
  calculateTrustScore,
  classifyTrustScore,
  TrustScoreInput,
} from './analyzers/trust-score.calculator';

export interface ReviewData {
  productId:   string;
  marketplace: string;
  rating:      number | null;
  reviewCount: number | null;
  stars5?:     number | null;
  stars4?:     number | null;
  stars3?:     number | null;
  stars2?:     number | null;
  stars1?:     number | null;
  /** Textos de reviews individuais para extração de keywords */
  reviewTexts?: string[];
}

export interface ReviewSummaryResult {
  productId:       string;
  marketplace:     string;
  rating:          number | null;
  reviewCount:     number | null;
  trustScore:      number;
  trustLabel:      string;
  trustColor:      string;
  trustEmoji:      string;
  trustFactors:    Record<string, number>;
  topPositive:     Array<{ keyword: string; count: number; category: string }>;
  topNegative:     Array<{ keyword: string; count: number; category: string }>;
}

@Injectable()
export class ReviewIntelligenceService {
  private readonly logger  = new Logger(ReviewIntelligenceService.name);
  private readonly enabled: boolean;

  constructor(
    private readonly prisma:    PrismaService,
    private readonly eventBus:  EventBusService,
    private readonly config:    ConfigService,
  ) {
    this.enabled = this.config.get<boolean>('features.reviewIntel') ?? false;
  }

  /**
   * Processa e persiste o resumo de reviews de um produto.
   * Calcula Trust Score e extrai keyword signals.
   */
  async processReviews(data: ReviewData): Promise<ReviewSummaryResult> {
    if (!this.enabled) {
      this.logger.debug('[review] FEATURE_REVIEW_INTEL desabilitada — pulando análise');
      // Retorna resultado mínimo sem persistir nem chamar análise
      return {
        productId:    data.productId,
        marketplace:  data.marketplace,
        rating:       data.rating,
        reviewCount:  data.reviewCount,
        trustScore:   0,
        trustLabel:   'Desabilitado',
        trustColor:   'gray',
        trustEmoji:   '—',
        trustFactors: {},
        topPositive:  [],
        topNegative:  [],
      };
    }

    // Extrai keyword signals dos textos de review disponíveis
    const textSignals = (data.reviewTexts ?? []).map((text) =>
      extractKeywordSignals(text),
    );

    const { topPositive, topNegative } = textSignals.length > 0
      ? aggregateKeywordSignals(textSignals)
      : { topPositive: [], topNegative: [] };

    // Agrega signals para o Trust Score
    const aggregatedSignals = this.aggregateSignals(textSignals);

    // Calcula Trust Score
    const trustInput: TrustScoreInput = {
      rating:      data.rating,
      reviewCount: data.reviewCount,
      starsDistribution: {
        stars1: data.stars1 ?? null,
        stars2: data.stars2 ?? null,
        stars3: data.stars3 ?? null,
        stars4: data.stars4 ?? null,
        stars5: data.stars5 ?? null,
      },
      keywordSignals: aggregatedSignals,
    };

    const { score: trustScore, factors } = calculateTrustScore(trustInput);
    const { label, color, emoji }         = classifyTrustScore(trustScore);

    const prevSummary = await this.prisma.reviewSummary.findUnique({
      where: { productId_marketplace: { productId: data.productId, marketplace: data.marketplace } },
      select: { trustScore: true },
    });

    // Persiste no banco
    await this.prisma.reviewSummary.upsert({
      where: {
        productId_marketplace: {
          productId:   data.productId,
          marketplace: data.marketplace,
        },
      },
      update: {
        rating:          data.rating,
        reviewCount:     data.reviewCount,
        stars5:          data.stars5,
        stars4:          data.stars4,
        stars3:          data.stars3,
        stars2:          data.stars2,
        stars1:          data.stars1,
        positiveKeywords: JSON.stringify(topPositive),
        negativeKeywords: JSON.stringify(topNegative),
        trustScore,
        trustFactors:    JSON.stringify(factors),
        scrapedAt:       new Date(),
      },
      create: {
        productId:   data.productId,
        marketplace: data.marketplace,
        rating:      data.rating,
        reviewCount: data.reviewCount,
        stars5:      data.stars5,
        stars4:      data.stars4,
        stars3:      data.stars3,
        stars2:      data.stars2,
        stars1:      data.stars1,
        positiveKeywords: JSON.stringify(topPositive),
        negativeKeywords: JSON.stringify(topNegative),
        trustScore,
        trustFactors:    JSON.stringify(factors),
      },
    });

    // Emite evento se o Trust Score mudou significativamente
    const prevScore = prevSummary?.trustScore;
    if (prevScore != null && Math.abs(trustScore - prevScore) >= 5) {
      this.eventBus.emit(DOMAIN_EVENTS.TRUST_SCORE_CHANGED, {
        productId:   data.productId,
        marketplace: data.marketplace,
        oldScore:    prevScore,
        newScore:    trustScore,
      });

      this.logger.log(
        `[review] Trust Score mudou: ${data.productId} ${data.marketplace} — ${prevScore} → ${trustScore}`,
      );
    }

    this.eventBus.emit(DOMAIN_EVENTS.REVIEW_SCRAPED, {
      productId:   data.productId,
      marketplace: data.marketplace,
      rating:      data.rating,
      reviewCount: data.reviewCount,
    });

    return {
      productId:    data.productId,
      marketplace:  data.marketplace,
      rating:       data.rating,
      reviewCount:  data.reviewCount,
      trustScore,
      trustLabel:   label,
      trustColor:   color,
      trustEmoji:   emoji,
      trustFactors: factors,
      topPositive,
      topNegative,
    };
  }

  /** Busca o resumo de reviews de um produto (todos os marketplaces) */
  async getByProduct(productId: string): Promise<any[]> {
    const summaries = await this.prisma.reviewSummary.findMany({
      where: { productId },
      orderBy: { trustScore: 'desc' },
    });

    return summaries.map((s) => ({
      ...s,
      positiveKeywords: this.parseJson(s.positiveKeywords, []),
      negativeKeywords: this.parseJson(s.negativeKeywords, []),
      trustFactors:     this.parseJson(s.trustFactors, {}),
      ...classifyTrustScore(s.trustScore ?? 50),
    }));
  }

  /** Agrega signals de múltiplos textos em um único Record consolidado */
  private aggregateSignals(
    signals: ReturnType<typeof extractKeywordSignals>[],
  ): TrustScoreInput['keywordSignals'] {
    const categories = Object.keys(
      signals[0] ?? {},
    ) as KeywordCategory[];

    const aggregated = {} as TrustScoreInput['keywordSignals'];

    for (const cat of categories) {
      aggregated[cat] = {
        positiveScore: signals.reduce((s, sig) => s + (sig[cat]?.positiveScore ?? 0), 0),
        negativeScore: signals.reduce((s, sig) => s + (sig[cat]?.negativeScore ?? 0), 0),
        matches:       signals.flatMap((sig) => sig[cat]?.matches ?? []),
      };
    }

    // Garante todas as categorias mesmo sem signals
    const allCategories: KeywordCategory[] = [
      'durability', 'comfort', 'value_for_money', 'quality',
      'shipping', 'customer_service', 'sizing', 'safety', 'performance', 'aesthetics',
    ];
    for (const cat of allCategories) {
      if (!aggregated[cat]) {
        aggregated[cat] = { positiveScore: 0, negativeScore: 0, matches: [] };
      }
    }

    return aggregated;
  }

  private parseJson<T>(str: string, fallback: T): T {
    try { return JSON.parse(str); } catch { return fallback; }
  }
}
