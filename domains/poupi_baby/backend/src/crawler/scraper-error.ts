/**
 * scraper-error.ts
 *
 * Classificação canônica de erros de scraping.
 * Alimenta métricas, health score e observabilidade.
 */

export enum ScraperErrorType {
  TIMEOUT  = 'TIMEOUT',   // deadline ou axios timeout
  CAPTCHA  = 'CAPTCHA',   // desafio captcha detectado
  BLOCKED  = 'BLOCKED',   // 403, 429, IP bloqueado
  PARSING  = 'PARSING',   // seletor/JSON não encontrado
  NETWORK  = 'NETWORK',   // DNS, ECONNREFUSED, ENOTFOUND
  NO_PRICE = 'NO_PRICE',  // página carregou, preço ausente
  UNKNOWN  = 'UNKNOWN',
}

const PATTERNS: [RegExp, ScraperErrorType][] = [
  [/timeout|deadline|timed out/i,                             ScraperErrorType.TIMEOUT],
  [/captcha|robot check|verificar.*humano/i,                  ScraperErrorType.CAPTCHA],
  [/403|429|forbidden|blocked|unauthorized|rate.?limit/i,     ScraperErrorType.BLOCKED],
  [/econnrefused|enotfound|dns|network|socket/i,              ScraperErrorType.NETWORK],
  [/pre[çc]o n[ãa]o encontrado|no.?price|todas.*estratégia/i, ScraperErrorType.NO_PRICE],
  [/parse|seletor|selector|json|estratégia|falha/i,           ScraperErrorType.PARSING],
];

/**
 * Classifica um erro textual no enum canônico.
 * Retorna UNKNOWN se nenhum padrão casar.
 */
export function classifyError(error: string | null | undefined): ScraperErrorType {
  if (!error) return ScraperErrorType.UNKNOWN;
  for (const [pattern, type] of PATTERNS) {
    if (pattern.test(error)) return type;
  }
  return ScraperErrorType.UNKNOWN;
}

/** Serializa um mapa de contagens para JSON compacto */
export function serializeBreakdown(map: Partial<Record<ScraperErrorType, number>>): string {
  return JSON.stringify(map);
}

/** Deserializa e garante que todas as chaves existam */
export function deserializeBreakdown(raw: string | null): Record<ScraperErrorType, number> {
  const zero = Object.fromEntries(
    Object.values(ScraperErrorType).map((k) => [k, 0]),
  ) as Record<ScraperErrorType, number>;

  if (!raw) return zero;
  try {
    return { ...zero, ...(JSON.parse(raw) as Partial<Record<ScraperErrorType, number>>) };
  } catch {
    return zero;
  }
}
