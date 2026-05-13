/**
 * Catálogo de eventos de domínio do Poupi.
 * Convenção: <DOMÍNIO>.<AÇÃO> em snake_case.
 *
 * Regras:
 * - Eventos são imutáveis após dispatch
 * - Handlers não devem lançar exceções (log e continua)
 * - Eventos de domínio são internos; nunca expostos via HTTP
 */

export const DOMAIN_EVENTS = {
  // ── Offers / Preços ──────────────────────────────────────────────────
  /** Preço de uma oferta foi atualizado pelo scraper */
  OFFER_PRICE_UPDATED:   'offer.price_updated',
  /** Oferta voltou ao estoque */
  OFFER_BACK_IN_STOCK:   'offer.back_in_stock',
  /** Oferta saiu do estoque */
  OFFER_OUT_OF_STOCK:    'offer.out_of_stock',
  /** Falha de scraping para uma oferta */
  OFFER_SCRAPE_FAILED:   'offer.scrape_failed',

  // ── Deal Intelligence ─────────────────────────────────────────────────
  /** Deal Score foi recalculado */
  DEAL_SCORE_CALCULATED: 'deal.score_calculated',
  /** Deal Score atingiu threshold alto (>= 75) */
  DEAL_SCORE_HIGH:       'deal.score_high',

  // ── Review Intelligence ───────────────────────────────────────────────
  /** Reviews de um produto foram coletadas */
  REVIEW_SCRAPED:        'review.scraped',
  /** Trust Score mudou significativamente (>= 5pts) */
  TRUST_SCORE_CHANGED:   'review.trust_score_changed',

  // ── Alertas ──────────────────────────────────────────────────────────
  /** Alerta foi disparado (meta atingida) */
  ALERT_TRIGGERED:       'alert.triggered',
  /** Novo alerta criado por um usuário */
  ALERT_CREATED:         'alert.created',
  /** Produto atingiu nova minima historica */
  ALERT_NEW_LOWEST_PRICE: 'alert.new_lowest_price',
  /** Produto teve queda relevante de preco */
  ALERT_PRICE_DROP:       'alert.price_drop',
  /** Produto monitorado voltou ao estoque */
  ALERT_RESTOCKED:        'alert.restocked',

  // ── AI Ops ───────────────────────────────────────────────────────────
  /** Incidente detectado pelo AI Ops */
  INCIDENT_DETECTED:     'ai-ops.incident_detected',
  /** Incidente marcado como resolvido */
  INCIDENT_RESOLVED:     'ai-ops.incident_resolved',

  // ── Billing ──────────────────────────────────────────────────────────
  SUBSCRIPTION_ACTIVATED: 'billing.subscription_activated',
  SUBSCRIPTION_CANCELLED: 'billing.subscription_cancelled',
  PLAN_UPGRADED:           'billing.plan_upgraded',

  // ── Analytics ────────────────────────────────────────────────────────
  USER_EVENT:            'analytics.user_event',
} as const;

export type DomainEventType = typeof DOMAIN_EVENTS[keyof typeof DOMAIN_EVENTS];

/** Envelope padrão de todos os eventos de domínio */
export interface DomainEvent<T = unknown> {
  readonly type:      DomainEventType;
  readonly payload:   T;
  readonly timestamp: Date;
  /** ID de correlação para rastrear fluxos cross-módulo */
  readonly traceId:   string;
}

// ── Payloads tipados ──────────────────────────────────────────────────────────

export interface OfferPriceUpdatedPayload {
  offerId:      string;
  productId:    string;
  marketplace:  string;
  oldPrice:     number | null;
  newPrice:     number;
  availability: boolean;
}

export interface OfferScrapeFailedPayload {
  offerId:     string;
  marketplace: string;
  errorType:   string;
  errorMsg:    string;
  attemptsMade: number;
}

export interface DealScoreCalculatedPayload {
  offerId:    string;
  productId:  string;
  marketplace: string;
  score:      number;
  label:      string;
}

export interface AlertTriggeredPayload {
  alertId:      string;
  userId:       string;
  productId:    string;
  marketplace:  string;
  currentPrice: number;
  targetPrice:  number;
  dealScore?:   number;
}

export type SmartAlertType = 'NEW_LOWEST_PRICE' | 'PRICE_DROP' | 'RESTOCKED';

export interface SmartAlertPayload {
  userId:        string;
  productId:     string;
  offerId:       string;
  marketplace:   string;
  type:          SmartAlertType;
  currentPrice:  number;
  previousPrice: number | null;
  productTitle:  string;
  productUrl:    string;
  productImageUrl?: string | null;
  reason:        string;
}

export interface IncidentDetectedPayload {
  incidentId:   string;
  marketplace:  string;
  severity:     string;
  incidentType: string;
}

export interface ReviewScrapedPayload {
  productId:   string;
  marketplace: string;
  rating:      number | null;
  reviewCount: number | null;
}
