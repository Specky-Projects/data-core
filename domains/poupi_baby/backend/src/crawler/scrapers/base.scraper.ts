/**
 * base.scraper.ts
 *
 * Utilitários compartilhados entre todos os scrapers:
 *
 *  - Pool de User-Agents atualizado (Chrome 130+, Firefox 132+, Safari 18+)
 *  - Perfis de browser completos com Client Hints (Sec-CH-UA)
 *  - Headers realistas por marketplace com Referer encadeado
 *  - humanDelay(): distribuição log-normal simulando comportamento humano
 *  - fetchPage: retry + backoff exponencial + jitter
 *  - fetchWithTimeout: Promise.race() — mata páginas lentas
 *  - detectBlock(): identifica CAPTCHA, bloqueio, bot-detection
 *  - parsePrice: parser robusto de preço BR
 *  - ScrapedProduct: resultado padronizado
 */

import axios, { AxiosError } from 'axios';

// ---------------------------------------------------------------------------
// Perfis de browser completos
// Cada perfil agrupa UA + Client Hints coerentes entre si
// (Chrome UA + Sec-CH-UA do Chrome; Safari não envia Client Hints)
// ---------------------------------------------------------------------------

interface BrowserProfile {
  userAgent: string;
  secChUa?: string;
  secChUaMobile: string;
  secChUaPlatform: string;
  /** Plataforma para Sec-Fetch-* (afeta alguns headers adicionais) */
  platform: 'windows' | 'mac' | 'linux';
}

const BROWSER_PROFILES: BrowserProfile[] = [
  // Chrome 130 / Windows
  {
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
    secChUa: '"Chromium";v="130", "Google Chrome";v="130", "Not?A_Brand";v="99"',
    secChUaMobile: '?0',
    secChUaPlatform: '"Windows"',
    platform: 'windows',
  },
  // Chrome 131 / Windows
  {
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    secChUa: '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
    secChUaMobile: '?0',
    secChUaPlatform: '"Windows"',
    platform: 'windows',
  },
  // Chrome 130 / macOS
  {
    userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
    secChUa: '"Chromium";v="130", "Google Chrome";v="130", "Not?A_Brand";v="99"',
    secChUaMobile: '?0',
    secChUaPlatform: '"macOS"',
    platform: 'mac',
  },
  // Chrome 131 / macOS
  {
    userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    secChUa: '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
    secChUaMobile: '?0',
    secChUaPlatform: '"macOS"',
    platform: 'mac',
  },
  // Edge 130 / Windows
  {
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0',
    secChUa: '"Chromium";v="130", "Microsoft Edge";v="130", "Not?A_Brand";v="99"',
    secChUaMobile: '?0',
    secChUaPlatform: '"Windows"',
    platform: 'windows',
  },
  // Firefox 132 / Windows
  {
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0',
    // Firefox não envia Sec-CH-UA
    secChUaMobile: '?0',
    secChUaPlatform: '"Windows"',
    platform: 'windows',
  },
  // Firefox 132 / macOS
  {
    userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 14.7; rv:132.0) Gecko/20100101 Firefox/132.0',
    secChUaMobile: '?0',
    secChUaPlatform: '"macOS"',
    platform: 'mac',
  },
  // Safari 18 / macOS
  {
    userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_7_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Safari/605.1.15',
    // Safari não envia Sec-CH-UA
    secChUaMobile: '?0',
    secChUaPlatform: '"macOS"',
    platform: 'mac',
  },
  // Chrome 130 / Linux
  {
    userAgent: 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
    secChUa: '"Chromium";v="130", "Google Chrome";v="130", "Not?A_Brand";v="99"',
    secChUaMobile: '?0',
    secChUaPlatform: '"Linux"',
    platform: 'linux',
  },
];

// ---------------------------------------------------------------------------
// Perfis de header por marketplace
// Cada marketplace tem um Referer e Accept realístico para a navegação normal
// ---------------------------------------------------------------------------

interface MarketplaceHeaderProfile {
  referer: string;
  acceptLanguage: string;
  extraHeaders?: Record<string, string>;
}

const MARKETPLACE_PROFILES: Record<string, MarketplaceHeaderProfile> = {
  amazon: {
    referer: 'https://www.amazon.com.br/',
    acceptLanguage: 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
  },
  mercadolivre: {
    referer: 'https://www.mercadolivre.com.br/',
    acceptLanguage: 'pt-BR,pt;q=0.9',
    extraHeaders: {
      'X-Requested-With': 'XMLHttpRequest',
    },
  },
  kabum: {
    referer: 'https://www.kabum.com.br/',
    acceptLanguage: 'pt-BR,pt;q=0.9',
  },
  magalu: {
    referer: 'https://www.magazineluiza.com.br/',
    acceptLanguage: 'pt-BR,pt;q=0.9',
  },
  drogasil: {
    referer: 'https://www.drogasil.com.br/',
    acceptLanguage: 'pt-BR,pt;q=0.9',
  },
  paguemenos: {
    referer: 'https://www.paguemenos.com.br/',
    acceptLanguage: 'pt-BR,pt;q=0.9',
  },
  consultaremedios: {
    referer: 'https://consultaremedios.com.br/',
    acceptLanguage: 'pt-BR,pt;q=0.9',
  },
  farma22: {
    referer: 'https://www.farma22.com.br/',
    acceptLanguage: 'pt-BR,pt;q=0.9',
  },
  panvel: {
    referer: 'https://www.panvel.com/',
    acceptLanguage: 'pt-BR,pt;q=0.9',
  },
  nissei: {
    referer: 'https://www.farmaciasnissei.com.br/',
    acceptLanguage: 'pt-BR,pt;q=0.9',
  },
  ultrafarma: {
    referer: 'https://www.ultrafarma.com.br/',
    acceptLanguage: 'pt-BR,pt;q=0.9',
  },
  drogariaspacheco: {
    referer: 'https://www.drogariaspacheco.com.br/',
    acceptLanguage: 'pt-BR,pt;q=0.9',
  },
  drogariasaopaulo: {
    referer: 'https://www.drogariasaopaulo.com.br/',
    acceptLanguage: 'pt-BR,pt;q=0.9',
  },
};

/** Retorna um perfil de browser aleatório do pool */
function randomProfile(): BrowserProfile {
  return BROWSER_PROFILES[Math.floor(Math.random() * BROWSER_PROFILES.length)];
}

/**
 * Monta o conjunto de headers realistas para uma requisição.
 * Mistura perfil de browser + perfil de marketplace + extras opcionais.
 */
export function getRandomHeaders(
  marketplace?: string,
  extra: Record<string, string> = {},
): Record<string, string> {
  const profile  = randomProfile();
  const mpProfile = marketplace ? MARKETPLACE_PROFILES[marketplace] : null;

  const headers: Record<string, string> = {
    'User-Agent': profile.userAgent,
    Accept: 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': mpProfile?.acceptLanguage ?? 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
    'Accept-Encoding': 'gzip, deflate, br, zstd',
    Connection: 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': mpProfile ? 'same-origin' : 'none',
    'Sec-Fetch-User': '?1',
    'Cache-Control': 'max-age=0',
    DNT: '1',
  };

  // Client Hints — apenas para browsers Chromium
  if (profile.secChUa) {
    headers['Sec-CH-UA']          = profile.secChUa;
    headers['Sec-CH-UA-Mobile']   = profile.secChUaMobile;
    headers['Sec-CH-UA-Platform'] = profile.secChUaPlatform;
  }

  // Referer realista de marketplace (simula navegação dentro do site)
  if (mpProfile?.referer) {
    headers['Referer'] = mpProfile.referer;
  }

  // Headers extras do marketplace
  if (mpProfile?.extraHeaders) {
    Object.assign(headers, mpProfile.extraHeaders);
  }

  return { ...headers, ...extra };
}

// ---------------------------------------------------------------------------
// Delay humanizado — distribuição log-normal
//
// Humanos NÃO clicam em intervalos uniformes. A distribuição log-normal
// modela bem o comportamento: maioria dos cliques em ~300-800ms,
// cauda longa para leituras mais longas.
// ---------------------------------------------------------------------------

/**
 * Delay com distribuição log-normal (mais realista que uniforme).
 *
 * @param minMs   Mínimo absoluto em ms (default: 300)
 * @param maxMs   Máximo absoluto em ms (default: 2500)
 * @param mu      Média do log (default: 6.2 ≈ 490ms)
 * @param sigma   Desvio do log (default: 0.6)
 */
export async function humanDelay(
  minMs = 300,
  maxMs = 2500,
  mu = 6.2,
  sigma = 0.6,
): Promise<void> {
  // Box-Muller para normal padrão → log-normal
  const u1 = Math.random();
  const u2 = Math.random();
  const z  = Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2);
  const ms = Math.round(Math.exp(mu + sigma * z));
  const clamped = Math.max(minMs, Math.min(maxMs, ms));
  await new Promise((r) => setTimeout(r, clamped));
}

export async function randomSleep(minMs = 3_000, maxMs = 12_000): Promise<void> {
  const min = Math.max(0, Math.min(minMs, maxMs));
  const max = Math.max(min, maxMs);
  const ms = Math.round(min + Math.random() * (max - min));
  await new Promise((r) => setTimeout(r, ms));
}

/**
 * Jitter adicional entre retries (evita padrão de request regular).
 * Retorna um delay base + ruído aleatório de até 50%.
 */
function jitteredDelay(baseMs: number): number {
  return Math.round(baseMs * (1 + Math.random() * 0.5));
}

// ---------------------------------------------------------------------------
// Detecção de bloqueio / CAPTCHA
// ---------------------------------------------------------------------------

const BLOCK_PATTERNS: RegExp[] = [
  /captcha/i,
  /bot.check|bot.detection|are.you.a.robot|not.a.robot/i,
  /access.denied|acesso.negado/i,
  /cloudflare.*challenge/i,
  /just.a.moment/i,           // Cloudflare waiting room
  /enable.*javascript/i,
  /please.verify.you.are.human/i,
  /too.many.requests/i,
  /rate.limit/i,
  /blocked.by.*security/i,
  /bot.*traffic/i,
];

/**
 * Retorna true se o HTML indica que fomos bloqueados / detectados como bot.
 */
export function detectBlock(html: string): boolean {
  if (!html || html.length < 200) return true; // resposta vazia ou ínfima = bloqueio
  const sample = html.slice(0, 5000).toLowerCase();
  return BLOCK_PATTERNS.some((p) => p.test(sample));
}

// ---------------------------------------------------------------------------
// ScrapedProduct
// ---------------------------------------------------------------------------

export interface ScrapedProduct {
  success: boolean;
  price: number | null;
  name: string | null;
  imageUrl: string | null;
  originalPrice: number | null;
  availability: boolean;
  error: string | null;
  store: string | null;
  scrapedAt: Date;
  /** Calculado: percentual de desconto em relação ao preço original */
  discountPercentage: number | null;
  regionalOffers?: ScrapedRegionalOffer[];
  ean?: string | null;
  category?: string | null;
}

export interface ScrapedRegionalOffer {
  marketplaceName: string;
  marketplaceSlug: string;
  externalId: string;
  url: string;
  currentPrice: number;
  originalPrice: number | null;
  stock: number | null;
  availability: boolean;
}

export function makeProduct(partial: Partial<ScrapedProduct>): ScrapedProduct {
  const p: ScrapedProduct = {
    success: false,
    price: null,
    name: null,
    imageUrl: null,
    originalPrice: null,
    availability: true,
    error: null,
    store: null,
    scrapedAt: new Date(),
    discountPercentage: null,
    ...partial,
  };

  if (p.originalPrice && p.price && p.originalPrice > p.price) {
    p.discountPercentage = Math.round((1 - p.price / p.originalPrice) * 1000) / 10;
  }

  return p;
}

// ---------------------------------------------------------------------------
// parsePrice
// ---------------------------------------------------------------------------

/**
 * Converte strings de preço no formato brasileiro para float.
 *
 * Exemplos suportados:
 *   "R$ 1.299,90" → 1299.90
 *   "1299.90"     → 1299.90
 *   "1.299,90"    → 1299.90
 *   "1 299,90"    → 1299.90  (espaço como separador de milhar)
 */
export function parsePrice(text: string | null | undefined): number | null {
  if (!text) return null;

  let cleaned = text.replace(/[R$\s ]/g, '').trim();
  if (!cleaned) return null;

  // Formato BR: 1.299,90
  if (cleaned.includes(',')) {
    cleaned = cleaned.replace(/\./g, '').replace(',', '.');
  }

  // Remove caracteres não numéricos exceto ponto
  cleaned = cleaned.replace(/[^\d.]/g, '');

  const price = parseFloat(cleaned);
  if (isNaN(price) || price < 0.01 || price > 1_000_000) return null;

  return Math.round(price * 100) / 100;
}

// ---------------------------------------------------------------------------
// fetchPage
// ---------------------------------------------------------------------------

const BASE_RETRY_MS = 2_000;

function sleep(ms: number) {
  return new Promise((r) => setTimeout(r, ms));
}

/**
 * Faz GET HTTP com retry + backoff exponencial + jitter.
 * Detecta bloqueio por CAPTCHA e aumenta o delay antes de re-tentar.
 *
 * @param url        URL a ser acessada
 * @param headers    Headers customizados
 * @param maxRetries Número máximo de tentativas (padrão: 3)
 * @param timeoutMs  Timeout por requisição em ms (padrão: 15000)
 * @param marketplace Nome do marketplace para perfil de headers adaptativo
 */
export async function fetchPage(
  url: string,
  headers: Record<string, string> = getRandomHeaders(),
  maxRetries = 3,
  timeoutMs = 15_000,
  marketplace?: string,
): Promise<string | null> {
  let lastError = '';

  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    // Rotaciona headers a cada tentativa (UA diferente = menos fingerprinting)
    const reqHeaders = attempt > 1
      ? getRandomHeaders(marketplace)   // troca UA no retry
      : headers;

    try {
      // Delay humanizado antes de cada tentativa (exceto a primeira)
      if (attempt > 1) {
        const backoff = jitteredDelay(BASE_RETRY_MS * 2 ** (attempt - 1));
        await sleep(backoff);
      }

      await randomSleep();

      const response = await axios.get<string>(url, {
        headers: reqHeaders,
        timeout: timeoutMs,
        maxRedirects: 5,
        responseType: 'text',
        // Compressão automática
        decompress: true,
      });

      const html = response.data as string;

      // Verifica se recebemos um bloqueio/CAPTCHA
      if (detectBlock(html)) {
        lastError = 'CAPTCHA ou bloqueio detectado';
        console.warn(`[fetchPage] ${lastError} em ${url} (tentativa ${attempt})`);
        // Espera mais longa antes de retry ao detectar bloqueio
        if (attempt < maxRetries) {
          await sleep(jitteredDelay(15_000 * attempt));
        }
        continue;
      }

      return html;

    } catch (err) {
      const axiosErr = err as AxiosError;
      const status = axiosErr.response?.status;

      if (status === 429) {
        const wait = jitteredDelay(12_000 * attempt);
        lastError = `Rate limited (429) — aguardando ${(wait / 1000).toFixed(1)}s`;
        console.warn(`[fetchPage] ${lastError} para ${url}`);
        await sleep(wait);
        continue;
      }

      if (status === 503 || status === 502) {
        const wait = jitteredDelay(5_000 * attempt);
        lastError = `Serviço indisponível (${status}) — aguardando ${(wait / 1000).toFixed(1)}s`;
        await sleep(wait);
        continue;
      }

      if (status === 403 || status === 401) {
        lastError = `Acesso negado (${status}) — possível bloqueio por IP`;
        console.warn(`[fetchPage] ${lastError} para ${url}`);
        // Bloqueio permanente — não adianta retry rápido
        if (attempt < maxRetries) await sleep(jitteredDelay(20_000));
        continue;
      }

      lastError = axiosErr.message ?? String(err);

      if (attempt < maxRetries) {
        await sleep(jitteredDelay(BASE_RETRY_MS * 2 ** attempt));
      }
    }
  }

  console.error(`[fetchPage] Todas as ${maxRetries} tentativas falharam para ${url}: ${lastError}`);
  return null;
}

// ---------------------------------------------------------------------------
// fetchWithTimeout — Promise.race() mata páginas lentas
// ---------------------------------------------------------------------------

/**
 * Wrapper sobre fetchPage que adiciona um deadline absoluto via Promise.race().
 * Garante que o total de retries nunca ultrapasse `totalTimeoutMs`.
 */
export function fetchWithTimeout(
  url: string,
  headers: Record<string, string> = getRandomHeaders(),
  options: {
    perRequestMs?:  number;
    totalTimeoutMs?: number;
    maxRetries?:    number;
    marketplace?:   string;
  } = {},
): Promise<string | null> {
  const {
    perRequestMs   = 12_000,
    totalTimeoutMs = 35_000,
    maxRetries     = 3,
    marketplace,
  } = options;

  const fetchPromise = fetchPage(url, headers, maxRetries, perRequestMs, marketplace);

  const timeoutPromise = new Promise<null>((resolve) =>
    setTimeout(() => {
      console.warn(`[fetchWithTimeout] Deadline de ${totalTimeoutMs}ms atingido para ${url}`);
      resolve(null);
    }, totalTimeoutMs),
  );

  return Promise.race([fetchPromise, timeoutPromise]);
}

// Backwards compat — exporta USER_AGENTS e BASE_HEADERS para scrapers legados
export const USER_AGENTS: string[] = BROWSER_PROFILES.map((p) => p.userAgent);
export const BASE_HEADERS: Record<string, string> = {
  Accept: 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
  'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
  'Accept-Encoding': 'gzip, deflate, br',
};
