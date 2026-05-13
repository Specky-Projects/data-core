export type ScrapeErrorType =
  | 'BLOCKED'
  | 'CAPTCHA'
  | 'RATE_LIMIT'
  | 'PARSER_FAILED'
  | 'PRODUCT_NOT_FOUND'
  | 'OUT_OF_STOCK'
  | 'NETWORK_ERROR'
  | 'PROXY_ERROR'
  | 'TIMEOUT'
  | 'CIRCUIT_BREAKER_OPEN'
  | 'UNKNOWN';

export function classifyScrapeError(input: {
  statusCode?: number;
  error?: string | null;
  html?: string | null;
}): ScrapeErrorType {
  const text = `${input.error ?? ''} ${input.html?.slice(0, 5000) ?? ''}`.toLowerCase();

  if (input.statusCode === 429 || /rate.limit|too.many.requests|429/.test(text)) return 'RATE_LIMIT';
  if (/captcha|verify.you.are.human|recaptcha|hcaptcha/.test(text)) return 'CAPTCHA';
  if ([401, 403].includes(input.statusCode ?? 0) || /access.denied|acesso.negado|blocked|bloqueio|bot/.test(text)) {
    return 'BLOCKED';
  }
  if (/circuit_breaker_open/.test(text)) return 'CIRCUIT_BREAKER_OPEN';
  if (/proxy|tunnel|socks/.test(text)) return 'PROXY_ERROR';
  if (/timeout|timed out|etimedout/.test(text)) return 'TIMEOUT';
  if (/econn|socket|network|getaddrinfo|enotfound|reset/.test(text)) return 'NETWORK_ERROR';
  if (/produto.nao.encontrado|product.not.found|404/.test(text) || input.statusCode === 404) return 'PRODUCT_NOT_FOUND';
  if (/sem.estoque|fora.de.estoque|out.of.stock|indisponivel/.test(text)) return 'OUT_OF_STOCK';
  if (/preco.nao.encontrado|parser|parse|selector/.test(text)) return 'PARSER_FAILED';

  return 'UNKNOWN';
}
