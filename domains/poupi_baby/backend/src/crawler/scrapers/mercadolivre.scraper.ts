/**
 * mercadolivre.scraper.ts
 *
 * Scraper do Mercado Livre Brasil.
 *
 * Estratégia:
 *   1. API pública do ML (api.mercadolibre.com/items/:id) — sem HTML, dados estruturados
 *   2. Fallback: HTML scraping via __NEXT_DATA__ / CSS selectors
 */

import * as cheerio from 'cheerio';
import {
  fetchPage,
  fetchWithTimeout,
  getRandomHeaders,
  detectBlock,
  humanDelay,
  makeProduct,
  parsePrice,
  ScrapedProduct,
} from './base.scraper';
import { runStrategies } from './strategy';

// ---------------------------------------------------------------------------
// Seletores CSS (fallback)
// ---------------------------------------------------------------------------

const PRICE_SELECTORS = [
  '.andes-money-amount__fraction',
  '.price-tag-fraction',
  '[class*="price-tag-fraction"]',
  '.ui-pdp-price__second-line .andes-money-amount__fraction',
  '.ui-pdp-price .andes-money-amount__fraction',
];

const CENTS_SELECTORS = [
  '.andes-money-amount__cents',
  '.price-tag-cents',
];

const ORIGINAL_PRICE_SELECTORS = [
  '.ui-pdp-price__original-value .andes-money-amount__fraction',
  '.price-tag-amount-discount .price-tag-fraction',
];

const TITLE_SELECTORS = [
  '.ui-pdp-title',
  'h1.ui-pdp-title',
  '[class*="item-title"]',
  'h1',
];

const IMAGE_SELECTORS = [
  '.ui-pdp-image.ui-pdp-gallery__figure__image',
  '.ui-pdp-gallery__figure img',
  'figure.ui-pdp-gallery__figure img',
];

const UNAVAILABILITY_KEYWORDS = [
  'produto indisponível',
  'sem estoque',
  'não disponível',
  'esgotado',
];

// ---------------------------------------------------------------------------
// Extração via JSON embutido
// ---------------------------------------------------------------------------

/** Busca recursivamente chaves de preço num objeto JSON aninhado */
function findPriceInJson(data: unknown, depth = 0): number | null {
  if (depth > 10 || !data || typeof data !== 'object') return null;

  const PRICE_KEYS = ['price', 'sale_price', 'standard_price', 'amount', 'value'];

  if (Array.isArray(data)) {
    for (const item of data.slice(0, 5)) {
      const found = findPriceInJson(item, depth + 1);
      if (found) return found;
    }
    return null;
  }

  const obj = data as Record<string, unknown>;

  for (const key of PRICE_KEYS) {
    if (typeof obj[key] === 'number' && (obj[key] as number) > 0) {
      return Math.round((obj[key] as number) * 100) / 100;
    }
  }

  for (const value of Object.values(obj)) {
    const found = findPriceInJson(value, depth + 1);
    if (found) return found;
  }

  return null;
}

function extractFromJson(html: string): { price: number | null; name: string | null } {
  const patterns = [
    /<script[^>]*id="__NEXT_DATA__"[^>]*>([\s\S]*?)<\/script>/,
    /<script[^>]*>window\.__PRELOADED_STATE__\s*=\s*([\s\S]*?)<\/script>/,
    /"item"\s*:\s*(\{[\s\S]*?"price"[\s\S]*?\})/,
  ];

  for (const pattern of patterns) {
    const match = html.match(pattern);
    if (!match) continue;

    try {
      const data = JSON.parse(match[1]);
      const price = findPriceInJson(data);

      // Tenta extrair o título do JSON também
      const nameMatch = JSON.stringify(data).match(/"title"\s*:\s*"([^"]{10,200})"/);
      const name = nameMatch ? nameMatch[1] : null;

      if (price) return { price, name };
    } catch { /* ignora parse errors */ }
  }

  return { price: null, name: null };
}

// ---------------------------------------------------------------------------
// Extratores CSS (fallback)
// ---------------------------------------------------------------------------

function extractPriceCSS($: cheerio.CheerioAPI): number | null {
  for (const sel of PRICE_SELECTORS) {
    const fraction = $(sel).first().text().trim();
    if (!fraction) continue;

    let cents = '00';
    for (const centsSel of CENTS_SELECTORS) {
      const c = $(centsSel).first().text().trim();
      if (c) { cents = c.padStart(2, '0'); break; }
    }

    return parsePrice(`${fraction},${cents}`);
  }
  return null;
}

function extractOriginalPriceCSS($: cheerio.CheerioAPI): number | null {
  for (const sel of ORIGINAL_PRICE_SELECTORS) {
    const text = $(sel).first().text().trim();
    const price = parsePrice(text);
    if (price) return price;
  }
  return null;
}

function extractTitle($: cheerio.CheerioAPI): string | null {
  for (const sel of TITLE_SELECTORS) {
    const text = $(sel).first().text().trim().replace(/\s+/g, ' ');
    if (text && text.length > 3) return text;
  }
  return null;
}

function extractImage($: cheerio.CheerioAPI): string | null {
  for (const sel of IMAGE_SELECTORS) {
    const el = $(sel).first();
    const src = el.attr('data-zoom') || el.attr('src');
    // Remove parâmetros de redimensionamento do ML
    if (src) return src.replace(/_\d+x\d+\.\w+/, (m) => m.replace(/\d+x\d+/, '0x0'));
  }
  return null;
}

function checkAvailability($: cheerio.CheerioAPI): boolean {
  const bodyText = $('body').text().toLowerCase();
  return !UNAVAILABILITY_KEYWORDS.some((kw) => bodyText.includes(kw));
}

// ---------------------------------------------------------------------------
// Função principal
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// API pública do Mercado Livre
// ---------------------------------------------------------------------------

/** Extrai o ID do item da URL (ex: MLB-5391681744 ou MLB5391681744) */
function extractItemId(url: string): string | null {
  const match = url.match(/MLB-?(\d+)/i);
  return match ? `MLB${match[1]}` : null;
}

interface MlApiItem {
  id: string;
  title: string;
  price: number;
  original_price: number | null;
  condition: string;
  status: string;
  thumbnail: string;
  secure_thumbnail: string;
  permalink: string;
}

// Cache do app token (evita chamar oauth a cada request)
let _mlToken: string | null = null;
let _mlTokenExpiry = 0;

async function getMlAppToken(): Promise<string | null> {
  const clientId = process.env.ML_CLIENT_ID;
  const clientSecret = process.env.ML_CLIENT_SECRET;
  if (!clientId || !clientSecret) return null;

  if (_mlToken && Date.now() < _mlTokenExpiry) return _mlToken;

  try {
    const res = await fetch('https://api.mercadolibre.com/oauth/token', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded', accept: 'application/json' },
      body: new URLSearchParams({
        grant_type: 'client_credentials',
        client_id: clientId,
        client_secret: clientSecret,
      }),
    });
    if (!res.ok) return null;
    const data = await res.json() as { access_token: string; expires_in: number };
    _mlToken = data.access_token;
    _mlTokenExpiry = Date.now() + (data.expires_in - 300) * 1000; // 5min de margem
    return _mlToken;
  } catch {
    return null;
  }
}

async function fetchFromApi(itemId: string): Promise<MlApiItem | null> {
  const token = await getMlAppToken();
  const headers: Record<string, string> = { 'User-Agent': 'Mozilla/5.0' };
  if (token) headers['Authorization'] = `Bearer ${token}`;

  try {
    const res = await fetch(`https://api.mercadolibre.com/items/${itemId}`, { headers });
    if (!res.ok) return null;
    return res.json() as Promise<MlApiItem>;
  } catch {
    return null;
  }
}

// ---------------------------------------------------------------------------
// Função principal
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// Estratégias formais
// ---------------------------------------------------------------------------

type Extracted = {
  price: number; name: string | null; imageUrl: string | null;
  originalPrice: number | null; availability: boolean;
};

async function strategyMlApi(url: string): Promise<Extracted | null> {
  const itemId = extractItemId(url);
  if (!itemId) return null;

  const item = await fetchFromApi(itemId);
  if (!item || item.price <= 0) return null;

  return {
    price: item.price,
    name: item.title,
    imageUrl: item.secure_thumbnail || item.thumbnail || null,
    originalPrice: item.original_price ?? null,
    availability: item.status === 'active',
  };
}

async function strategyHtmlJson(url: string): Promise<Extracted | null> {
  await humanDelay(300, 1000);
  const html = await fetchWithTimeout(
    url,
    getRandomHeaders('mercadolivre'),
    { perRequestMs: 12_000, totalTimeoutMs: 35_000, marketplace: 'mercadolivre' },
  );
  if (!html || detectBlock(html)) return null;

  const { price, name } = extractFromJson(html);
  if (!price) return null;

  const $ = cheerio.load(html);
  return {
    price,
    name,
    imageUrl: extractImage($),
    originalPrice: extractOriginalPriceCSS($),
    availability: checkAvailability($),
  };
}

async function strategyHtmlCSS(url: string): Promise<Extracted | null> {
  await humanDelay(700, 1800);
  const html = await fetchWithTimeout(
    url,
    getRandomHeaders('mercadolivre'),
    { perRequestMs: 12_000, totalTimeoutMs: 35_000, marketplace: 'mercadolivre' },
  );
  if (!html || detectBlock(html)) return null;

  const $ = cheerio.load(html);
  const price = extractPriceCSS($);
  if (!price) return null;

  return {
    price,
    name: extractTitle($),
    imageUrl: extractImage($),
    originalPrice: extractOriginalPriceCSS($),
    availability: checkAvailability($),
  };
}

// ---------------------------------------------------------------------------
// Função principal
// ---------------------------------------------------------------------------

export async function scrapeMercadoLivre(url: string): Promise<ScrapedProduct> {
  const result = await runStrategies<Extracted>(
    [
      () => strategyMlApi(url),
      () => strategyHtmlJson(url),
      () => strategyHtmlCSS(url),
    ],
    'mercadolivre',
  );

  if (result) return makeProduct({ success: true, store: 'mercadolivre', ...result });
  return makeProduct({ success: false, store: 'mercadolivre', error: 'Todas as estratégias falharam' });
}
