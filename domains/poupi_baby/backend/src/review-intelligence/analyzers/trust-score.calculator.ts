import { KeywordCategory, KeywordSignal } from '../config/review-keywords';

export interface TrustScoreInput {
  rating:           number | null;        // 0–5
  reviewCount:      number | null;
  starsDistribution: {                    // contagens por estrela
    stars1: number | null;
    stars2: number | null;
    stars3: number | null;
    stars4: number | null;
    stars5: number | null;
  };
  keywordSignals:   Record<KeywordCategory, KeywordSignal>;
}

export interface TrustScoreResult {
  score:   number;                       // 0–100
  factors: {
    ratingComponent:    number;          // 0–40
    sentimentComponent: number;          // 0–30
    volumeBonus:        number;          // 0–10
    consistencyBonus:   number;          // 0–10
    safetyPenalty:      number;          // ≤ 0
    bimodalPenalty:     number;          // ≤ 0
  };
}

/**
 * Calcula o Trust Score de um produto com base em reviews.
 *
 * Componentes:
 *   A. Rating quality (0–40): nota média ponderada por volume
 *   B. Sentiment (0–30): razão positivo/negativo das keywords
 *   C. Volume bonus (0–10): mais reviews = mais confiança
 *   D. Consistência (0–10): rating estável sem bimodalidade extrema
 *   E. Penalidade de segurança (até −40): problemas críticos (queimou, explodiu)
 *   F. Penalidade bimodal (até −10): muitas 5★ + muitas 1★ = suspeito
 */
export function calculateTrustScore(input: TrustScoreInput): TrustScoreResult {
  const rating      = input.rating      ?? 0;
  const reviewCount = input.reviewCount ?? 0;

  // ── A. Rating quality (0–40) ─────────────────────────────────────────
  const ratingComponent = (rating / 5) * 40;

  // ── B. Sentiment (0–30) ──────────────────────────────────────────────
  let positiveTotal = 0;
  let negativeTotal = 0;
  for (const data of Object.values(input.keywordSignals)) {
    positiveTotal += data.positiveScore;
    negativeTotal += data.negativeScore;
  }
  const sentimentRatio    = positiveTotal / Math.max(1, positiveTotal + negativeTotal);
  const sentimentComponent = sentimentRatio * 30;

  // ── C. Volume bonus (0–10) ───────────────────────────────────────────
  // log10(1) = 0, log10(10) = 1, log10(100) = 2, log10(1000) = 3
  const volumeBonus = Math.min(10, Math.log10(reviewCount + 1) * 5);

  // ── D. Consistência bonus (0–10) ─────────────────────────────────────
  const consistencyBonus = reviewCount > 50 && rating >= 4.0 ? 10 : 0;

  // ── E. Penalidade de segurança (até −40) ─────────────────────────────
  const safetySignal    = input.keywordSignals.safety;
  const hasSafetyIssues = safetySignal.negativeScore >= 3; // "queimou", "explodiu", etc.
  const safetyPenalty   = hasSafetyIssues ? -40 : 0;

  // ── F. Penalidade bimodal (até −10) ──────────────────────────────────
  const dist    = input.starsDistribution;
  const totalStars =
    (dist.stars1 ?? 0) + (dist.stars2 ?? 0) + (dist.stars3 ?? 0) +
    (dist.stars4 ?? 0) + (dist.stars5 ?? 0);

  let bimodalPenalty = 0;
  if (totalStars > 10) {
    const pct1 = (dist.stars1 ?? 0) / totalStars;
    const pct5 = (dist.stars5 ?? 0) / totalStars;
    // Muitas 5★ e muitas 1★ = distribuição suspeita (review bombing ou fake reviews)
    if (pct1 > 0.20 && pct5 > 0.60) bimodalPenalty = -10;
    else if (pct1 > 0.15 && pct5 > 0.70) bimodalPenalty = -5;
  }

  // ── Score final ───────────────────────────────────────────────────────
  const raw   = ratingComponent + sentimentComponent + volumeBonus + consistencyBonus + safetyPenalty + bimodalPenalty;
  const score = Math.round(Math.max(0, Math.min(100, raw)));

  return {
    score,
    factors: {
      ratingComponent:    Math.round(ratingComponent),
      sentimentComponent: Math.round(sentimentComponent),
      volumeBonus:        Math.round(volumeBonus),
      consistencyBonus,
      safetyPenalty,
      bimodalPenalty,
    },
  };
}

/** Classifica o Trust Score em label + cor */
export function classifyTrustScore(score: number): {
  label:      string;
  color:      string;
  emoji:      string;
  description: string;
} {
  if (score >= 90) return {
    label:       'Altamente confiável',
    color:       '#22c55e',
    emoji:       '🏆',
    description: 'Produto com excelente reputação e consistência de reviews.',
  };
  if (score >= 75) return {
    label:       'Muito confiável',
    color:       '#4ade80',
    emoji:       '✅',
    description: 'Produto bem avaliado com poucos problemas reportados.',
  };
  if (score >= 60) return {
    label:       'Confiável',
    color:       '#86efac',
    emoji:       '👍',
    description: 'Produto razoavelmente bem avaliado.',
  };
  if (score >= 40) return {
    label:       'Opiniões mistas',
    color:       '#fbbf24',
    emoji:       '⚠️',
    description: 'Reviews divididos — leia os comentários negativos com atenção.',
  };
  return {
    label:       'Reputação preocupante',
    color:       '#ef4444',
    emoji:       '🚨',
    description: 'Muitos problemas reportados. Considere alternativas.',
  };
}
