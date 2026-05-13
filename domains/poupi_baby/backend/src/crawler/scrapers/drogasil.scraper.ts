/**
 * drogasil.scraper.ts
 *
 * Funciona para Drogasil e Droga Raia (mesmo grupo, plataforma VTEX IO).
 *
 * Estratégias (em ordem):
 *   1. JSON-LD Product (VTEX sempre emite)
 *   2. window.__STATE__ JSON (VTEX state tree)
 *   3. CSS selectors (classes VTEX geradas com hash)
 */

import * as cheerio from 'cheerio';
import {
  fetchWithTimeout,
  getRandomHeaders,
  detectBlock,
  humanDelay,
  makeProduct,
  parsePrice,
  ScrapedProduct,
} from './base.scraper';
import {
  runStrategies,
  findProductJsonLd,
  extractFromProductJsonLd,
} from './strategy';

// ---------------------------------------------------------------------------
// Seletores CSS (VTEX IO — padrões parciais, hash muda por deploy)
// ---------------------------------------------------------------------------

const PRICE_SELECTORS = [
  '[class*="sellingPriceValue"]',
  '[class*="sellingPrice"]',
  '[class*="currencyContainer"]',
  '.vtex-product-price-1-x-sellingPriceValue',
  '.vtex-product-price-1-x-sellingPrice',
  'span[class*="Price"] span[class*="currencyContainer"]',
];

const ORIGINAL_PRICE_SELECTORS = [
  '[class*="listPriceValue"]',
  '.vtex-product-price-1-x-listPrice',
  'del [class*="currencyContainer"]',
  's [class*="Price"]',
];

const TITLE_SELECTORS = [
  '.vtex-store-components-3-x-productNameContainer h1',
  '[class*="productName"] h1',
  '[class*="ProductName"] h1',
  'h1[class*="Title"]',
  'h1',
];

const IMAGE_SELECTORS = [
  '.vtex-store-components-3-x-productImageTag',
  '[class*="productImageTag"]',
  '[class*="productImage"] img',
  'figure img[class*="product"]',
];

const UNAVAILABILITY = ['produto indisponível', 'esgotado', 'sem estoque', 'fora de estoque', 'indisponível'];

// ---------------------------------------------------------------------------
// Tipos internos
// ---------------------------------------------------------------------------

type Extracted = {
  price: number; name: string | null; imageUrl: string | null;
  originalPrice: number | null; availability: boolean;
};

// ---------------------------------------------------------------------------
// Shared fetch
// ---------------------------------------------------------------------------

function fetchHtml(url: string): Promise<string | null> {
  return fetchWithTimeout(
    url,
    getRandomHeaders('drogasil'),
    { perRequestMs: 12_000, totalTimeoutMs: 35_000, maxRetries: 3, marketplace: 'drogasil' },
  );
}

// ---------------------------------------------------------------------------
// Estratégias
// ---------------------------------------------------------------------------

async function strategyJsonLd(url: string): Promise<Extracted | null> {
  await humanDelay(200, 800);
  const html = await fetchHtml(url);
  if (!html || detectBlock(html)) return null;

  const block = findProductJsonLd(html);
  if (!block) return null;

  const ex = extractFromProductJsonLd(block);
  if (!ex.price) return null;

  const $ = cheerio.load(html);
  return {
    price: ex.price,
    name: ex.name,
    imageUrl: ex.imageUrl ?? extractImageCSS($),
    originalPrice: ex.originalPrice,
    availability: ex.availability,
  };
}

async function strategyVtexState(url: string): Promise<Extracted | null> {
  await humanDelay(500, 1200);
  const html = await fetchHtml(url);
  if (!html || detectBlock(html)) return null;

  const stateMatch = html.match(/window\.__STATE__\s*=\s*(\{[\s\S]*?});?\s*<\/script>/);
  if (!stateMatch) return null;

  try {
    const state = JSON.parse(stateMatch[1]) as Record<string, unknown>;

    let price: number | null = null;
    let originalPrice: number | null = null;
    let name: string | null = null;
    let imageUrl: string | null = null;
    let availability = true;

    for (const [key, val] of Object.entries(state)) {
      if (typeof val !== 'object' || !val) continue;
      const obj = val as Record<string, unknown>;

      if ((key.startsWith('Product:') || key.startsWith('SKU:')) && typeof obj.price === 'number') {
        if (!price || (obj.price as number) < price) price = obj.price as number;
      }
      if (typeof obj.listPrice === 'number' && obj.listPrice > 0) originalPrice = obj.listPrice as number;
      if (!name && typeof obj.productName === 'string' && (obj.productName as string).length > 3) name = obj.productName as string;
      if (!name && typeof obj.name === 'string' && (obj.name as string).length > 3 && key.startsWith('Product:')) name = obj.name as string;
      if (!imageUrl && typeof obj.imageUrl === 'string') imageUrl = obj.imageUrl as string;
      if (typeof obj.availability === 'string') availability = (obj.availability as string) !== 'unavailableWithoutDate';
    }

    if (!price) return null;

    return {
      price: Math.round(price * 100) / 100,
      name,
      imageUrl,
      originalPrice: originalPrice && originalPrice > price ? Math.round(originalPrice * 100) / 100 : null,
      availability,
    };
  } catch {
    return null;
  }
}

async function strategyCSS(url: string): Promise<Extracted | null> {
  await humanDelay(800, 2000);
  const html = await fetchHtml(url);
  if (!html || detectBlock(html)) return null;

  const $ = cheerio.load(html);
  const price = extractPriceCSS($);
  if (!price) return null;

  return {
    price,
    name: extractTitleCSS($),
    imageUrl: extractImageCSS($),
    originalPrice: extractOriginalPriceCSS($),
    availability: !UNAVAILABILITY.some((kw) => $('body').text().toLowerCase().includes(kw)),
  };
}

// ---------------------------------------------------------------------------
// Extratores CSS
// ---------------------------------------------------------------------------

function extractPriceCSS($: cheerio.CheerioAPI): number | null {
  for (const sel of PRICE_SELECTORS) {
    const price = parsePrice($(sel).first().text().trim());
    if (price) return price;
  }
  const match = $.html().match(/R\$\s*([\d.]+,\d{2})/);
  return match ? parsePrice(match[1]) : null;
}

function extractOriginalPriceCSS($: cheerio.CheerioAPI): number | null {
  for (const sel of ORIGINAL_PRICE_SELECTORS) {
    const price = parsePrice($(sel).first().text().trim());
    if (price) return price;
  }
  return null;
}

function extractTitleCSS($: cheerio.CheerioAPI): string | null {
  for (const sel of TITLE_SELECTORS) {
    const text = $(sel).first().text().trim().replace(/\s+/g, ' ');
    if (text && text.length > 3) return text;
  }
  return null;
}

function extractImageCSS($: cheerio.CheerioAPI): string | null {
  for (const sel of IMAGE_SELECTORS) {
    const src = $(sel).first().attr('src');
    if (src && !src.startsWith('data:')) return src;
  }
  return null;
}

// ---------------------------------------------------------------------------
// Função principal
// ---------------------------------------------------------------------------

export async function scrapeDrogasil(url: string): Promise<ScrapedProduct> {
  const store = url.includes('drogaraia') ? 'drogaraia' : 'drogasil';

  const result = await runStrategies<Extracted>(
    [
      () => strategyJsonLd(url),
      () => strategyVtexState(url),
      () => strategyCSS(url),
    ],
    store,
  );

  if (result) return makeProduct({ success: true, store, ...result });
  return makeProduct({ success: false, store, error: 'Todas as estratégias falharam' });
}
