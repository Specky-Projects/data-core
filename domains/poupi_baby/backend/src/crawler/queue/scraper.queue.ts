/**
 * scraper.queue.ts
 *
 * Definições centrais da fila de scraping com BullMQ.
 *
 * Estratégia de prioridade:
 *   1 — Sync manual forçado (POST /crawler/sync/:offerId)
 *   2 — Ofertas com alertas ativos (usuário esperando queda)
 *   3 — Sync automático padrão
 *
 * Retry com backoff exponencial:
 *   tentativa 1 → 30s
 *   tentativa 2 → 60s
 *   tentativa 3 → 120s
 *   tentativa 4 → 300s (dead-letter após esta)
 *
 * Dead-Letter: jobs com 4 falhas consecutivas são marcados como failed
 * e registrados no ScraperHealth. O scheduler não vai re-enfileirar
 * scrapers desativados (health < 20%).
 */

export const SCRAPER_QUEUE = 'scraper';
export const SCRAPER_DLQ   = 'scraper-dlq';

// ── Tipos de jobs ────────────────────────────────────────────────────────────

export interface SyncOfferJobData {
  offerId: string;
  marketplace: string;
  productUrl: string;
  triggeredBy: 'scheduler' | 'manual' | 'alert';
}

export interface SyncAllJobData {
  triggeredBy: 'scheduler' | 'manual';
}

export type ScraperJobData = SyncOfferJobData | SyncAllJobData;

// ── Prioridades ──────────────────────────────────────────────────────────────

export const PRIORITY = {
  MANUAL:   1,   // POST /crawler/sync/:offerId
  ALERT:    2,   // oferta com alerta ativo
  SCHEDULE: 3,   // sync automático do cron
} as const;

// ── Config de retry (BullMQ DefaultJobOptions) ───────────────────────────────

export const SCRAPER_JOB_DEFAULTS = {
  attempts: 3,
  backoff: {
    type: 'exponential' as const,
    delay: 180_000, // 3min base -> 3min, 6min, 12min
  },
  removeOnComplete: {
    age: 3600,    // mantém jobs completos por 1h para debug
    count: 200,
  },
  removeOnFail: {
    age: 86_400,  // mantém jobs falhos por 24h no DLQ virtual
    count: 500,
  },
} as const;
