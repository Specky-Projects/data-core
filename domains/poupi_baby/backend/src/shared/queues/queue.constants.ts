/**
 * queue.constants.ts
 *
 * Fonte única de nomes de filas BullMQ e tipos de jobs.
 * Importe daqui em vez de usar strings literais.
 *
 * Filas:
 *   scraper          — scraping de ofertas (já existia)
 *   deal-score       — (re)cálculo de deal score por oferta
 *   review-analyzer  — análise de reviews com keywords + trust score
 *   market-patterns  — cálculo de padrões de mercado
 *   ai-incident      — análise de incidente via IA (isolado do scraping)
 *   notification     — envio de emails / push / webhooks
 *   cleanup          — purge de dados antigos (métricas, eventos)
 */

// ── Nomes das filas ────────────────────────────────────────────────────────
export const DEAL_SCORE_QUEUE      = 'deal-score';
export const REVIEW_ANALYZER_QUEUE = 'review-analyzer';
export const MARKET_PATTERNS_QUEUE = 'market-patterns';
export const AI_INCIDENT_QUEUE     = 'ai-incident';
export const NOTIFICATION_QUEUE    = 'notification';
export const CLEANUP_QUEUE         = 'cleanup';

// ── Job types — Deal Score ─────────────────────────────────────────────────
export const DEAL_SCORE_JOB = 'calculate-deal-score';

export interface DealScoreJobData {
  offerId:    string;
  productId:  string;
  reason:     'price_updated' | 'manual' | 'schedule';
}

// ── Job types — Review Analyzer ───────────────────────────────────────────
export const REVIEW_ANALYZER_JOB = 'analyze-reviews';

export interface ReviewAnalyzerJobData {
  productId:    string;
  marketplace:  string;
  rating:       number | null;
  reviewCount:  number | null;
  stars5?:      number | null;
  stars4?:      number | null;
  stars3?:      number | null;
  stars2?:      number | null;
  stars1?:      number | null;
  reviewTexts?: string[];
  source:       'scraper' | 'manual';
}

// ── Job types — Market Patterns ───────────────────────────────────────────
export const MARKET_PATTERNS_JOB = 'compute-market-patterns';

export interface MarketPatternsJobData {
  productId:   string;
  marketplace: string;
  reason:      'price_updated' | 'schedule';
}

// ── Job types — AI Incident ───────────────────────────────────────────────
export const AI_INCIDENT_JOB = 'analyze-incident';

export interface AiIncidentJobData {
  marketplace:   string;
  successRate:   number;
  avgLatencyMs:  number;
  errorTypes:    Record<string, number>;
  sampleWindow:  number;  // minutos
  totalRequests: number;
}

// ── Job types — Notification ──────────────────────────────────────────────
export const NOTIFICATION_JOB = 'send-notification';

export type NotificationChannel = 'email' | 'push' | 'webhook';

export interface NotificationJobData {
  userId?:     string;                  // null = admin notification
  channel:     NotificationChannel;
  template:    string;                  // e.g. 'alert.triggered', 'deal.high_score'
  payload:     Record<string, unknown>;
  priority?:   'low' | 'normal' | 'high';
}

// ── Job types — Cleanup ───────────────────────────────────────────────────
export const CLEANUP_METRICS_JOB  = 'cleanup-scraper-metrics';
export const CLEANUP_EVENTS_JOB   = 'cleanup-user-events';
export const CLEANUP_INCIDENTS_JOB = 'cleanup-ai-incidents';

export interface CleanupJobData {
  type:         'scraper-metrics' | 'user-events' | 'ai-incidents';
  retentionDays: number;
}

// ── Default job options por fila ───────────────────────────────────────────
export const DEAL_SCORE_JOB_DEFAULTS = {
  attempts:    3,
  backoff:     { type: 'exponential' as const, delay: 5_000 },
  removeOnComplete: { count: 500 },
  removeOnFail:     { count: 100 },
};

export const REVIEW_ANALYZER_JOB_DEFAULTS = {
  attempts:    2,
  backoff:     { type: 'fixed' as const, delay: 10_000 },
  removeOnComplete: { count: 200 },
  removeOnFail:     { count: 50 },
};

export const MARKET_PATTERNS_JOB_DEFAULTS = {
  attempts:    2,
  backoff:     { type: 'exponential' as const, delay: 15_000 },
  removeOnComplete: { count: 200 },
  removeOnFail:     { count: 50 },
};

export const AI_INCIDENT_JOB_DEFAULTS = {
  attempts:    2,
  backoff:     { type: 'fixed' as const, delay: 30_000 },
  removeOnComplete: { count: 100 },
  removeOnFail:     { count: 50 },
};

export const NOTIFICATION_JOB_DEFAULTS = {
  attempts:    3,
  backoff:     { type: 'exponential' as const, delay: 5_000 },
  removeOnComplete: { count: 1_000 },
  removeOnFail:     { count: 200 },
};

export const CLEANUP_JOB_DEFAULTS = {
  attempts:    1,
  removeOnComplete: { count: 10 },
  removeOnFail:     { count: 10 },
};
