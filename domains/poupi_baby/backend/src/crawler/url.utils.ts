/**
 * url.utils.ts
 *
 * Utilitários de URL para o crawler:
 *   - normalizePrice()     Etapa 2.2 — preço sempre como number limpo
 *   - canonicalUrl()       Etapa 2.3 — URL sem params de rastreamento
 *   - extractExternalId()  Etapa 2.4 — ID real do produto no marketplace
 */

// ---------------------------------------------------------------------------
// 2.2 — normalizePrice
// ---------------------------------------------------------------------------

/**
 * Converte qualquer string de preço para número.
 *
 * Handles:
 *   "R$ 1.299,90"         → 1299.90
 *   "1.299,90"            → 1299.90
 *   "1299.90"             → 1299.90
 *   "1 299,90"            → 1299.90   (espaço como separador de milhar)
 *   "a partir de R$ 299"  → 299.00
 *   "12x de R$ 99,90"     → null      (preço parcelado — ambíguo, descartar)
 *   "GRÁTIS"              → null
 */
export function normalizePrice(raw: string | number | null | undefined): number | null {
  if (raw === null || raw === undefined) return null;
  if (typeof raw === 'number') {
    if (!isFinite(raw) || raw < 0.01 || raw > 1_000_000) return null;
    return Math.round(raw * 100) / 100;
  }

  let text = String(raw).trim();

  // Descarta preços parcelados — não sabemos o total real
  if (/\d+\s*x\s*(de\s*)?r?\$?\s*[\d.,]+/i.test(text)) return null;

  // Remove prefixos comuns antes do valor
  text = text.replace(/a partir de|por|preço:/gi, '').trim();

  // Remove símbolo de moeda e espaços não-breaking
  text = text.replace(/R\$|\$|BRL/gi, '').replace(/[\s ]/g, '');

  // Formato BR: 1.299,90  →  1299.90
  if (text.includes(',')) {
    text = text.replace(/\./g, '').replace(',', '.');
  }

  // Remove tudo que não seja dígito ou ponto
  text = text.replace(/[^\d.]/g, '');

  // Múltiplos pontos (erro de parse) → inválido
  if ((text.match(/\./g) ?? []).length > 1) return null;

  const price = parseFloat(text);
  if (isNaN(price) || price < 0.01 || price > 1_000_000) return null;

  return Math.round(price * 100) / 100;
}

// ---------------------------------------------------------------------------
// 2.3 — canonicalUrl
// ---------------------------------------------------------------------------

/** Params de rastreamento/afiliado a remover de qualquer URL */
const STRIP_PARAMS = new Set([
  // UTM (universal)
  'utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term', 'utm_id',
  // Ad networks
  'fbclid', 'gclid', 'msclkid', 'ttclid', 'twclid', '_ga', 'gbraid', 'wbraid',
  // Amazon
  'ref', 'ref_', 'tag', 'linkCode', 'linkId', 'camp', 'creative', 'creativeASIN',
  'pd_rd_r', 'pd_rd_w', 'pd_rd_wg', 'pf_rd_p', 'pf_rd_r', 'sr', 'qid',
  // Mercado Livre
  'position', 'search_layout', 'type', 'tracking_id', 'c_id',
  // Magazine Luiza
  'loja', 'seller_id',
  // Shopee / generic
  'offerType', 'sellerId', 'seller', 'variant', '_lhe', 'channel',
  // Analytics
  'mc_cid', 'mc_eid', 'yclid', 'igshid',
]);

/**
 * Retorna a URL canônica — sem params de rastreamento,
 * hostname sem www., sem trailing slash, params restantes ordenados.
 *
 * Preserva params funcionais do produto (ex: `cor=azul`).
 */
export function canonicalUrl(raw: string): string {
  let parsed: URL;
  try {
    parsed = new URL(raw);
  } catch {
    return raw;
  }

  // Remove tracking params
  for (const key of [...parsed.searchParams.keys()]) {
    if (STRIP_PARAMS.has(key.toLowerCase()) || key.startsWith('utm_')) {
      parsed.searchParams.delete(key);
    }
  }

  // Ordena params restantes (idempotência)
  parsed.searchParams.sort();

  // Remove www.
  parsed.hostname = parsed.hostname.replace(/^www\./, '');

  // Remove trailing slash do path (exceto root)
  if (parsed.pathname !== '/') {
    parsed.pathname = parsed.pathname.replace(/\/$/, '');
  }

  // Descarta hash (fragment) — irrelevante para produto
  parsed.hash = '';

  return parsed.toString();
}

// ---------------------------------------------------------------------------
// 2.4 — extractExternalId
// ---------------------------------------------------------------------------

/**
 * Extrai o ID real do produto no marketplace a partir da URL.
 * Este valor é usado como `externalId` na tabela `offers`
 * junto com `marketplaceId` para garantir unicidade real.
 *
 * Sem isso, dois usuários adicionando o mesmo produto via URLs
 * diferentes (UTM, variante) criariam duplicatas.
 */
export function extractExternalId(url: string, store: string): string {
  const clean = canonicalUrl(url);

  switch (store) {
    case 'amazon': {
      // /dp/ASIN ou /gp/product/ASIN  — ASIN = 10 chars alfanuméricos maiúsculos
      const m = clean.match(/\/(?:dp|gp\/product)\/([A-Z0-9]{10})(?:\/|$|\?)/);
      if (m) return m[1];
      break;
    }

    case 'mercadolivre': {
      // MLB-5391681744 ou MLB5391681744
      const m = clean.match(/MLB-?(\d{7,12})/i);
      if (m) return `MLB${m[1]}`;
      break;
    }

    case 'kabum': {
      // /produto/123456/nome-do-produto
      const m = clean.match(/\/produto\/(\d+)/);
      if (m) return `KABUM-${m[1]}`;
      break;
    }

    case 'magalu': {
      // Dois formatos conhecidos:
      //   /nome-produto/p/XXXXXX/   → código alfanumérico 6–8 chars
      //   /nome-produto-XXXXXX/p    → código no final do slug
      const m =
        clean.match(/\/p\/([a-z0-9]{5,10})\//i) ??
        clean.match(/-([a-z0-9]{6,8})\/p(?:\/|$|\?)/i);
      if (m) return `MAGALU-${m[1].toUpperCase()}`;
      break;
    }

    case 'drogasil':
    case 'drogaraia': {
      // /produto/nome-do-produto-XXXXXXXXXX/p
      const m = clean.match(/\/produto\/([^/]+)\/p(?:\/|$|\?)/);
      if (m) return `${store.toUpperCase()}-${m[1]}`;
      break;
    }
  }

  // Fallback: pathname limpa como ID (sem tracking, consistente)
  try {
    const { pathname } = new URL(clean);
    return pathname.replace(/^\//, '').replace(/\//g, '--').slice(0, 255) || clean.slice(0, 255);
  } catch {
    return clean.slice(0, 255);
  }
}
