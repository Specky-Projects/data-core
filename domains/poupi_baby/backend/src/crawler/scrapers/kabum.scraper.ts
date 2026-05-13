/**
 * kabum.scraper.ts
 *
 * Estratégias (em ordem):
 *   1. __NEXT_DATA__ JSON
 *   2. JSON-LD Product
 *   3. CSS selectors
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
  parseNextData,
  findProductJsonLd,
  extractFromProductJsonLd,
} from './strategy';

// ---------------------------------------------------------------------------
// Seletores CSS
// ---------------------------------------------------------------------------

const PRICE_SELECTORS = [
  '[data-testid="product-final-price"]',
  '[class*="finalPrice"]',
  '[class*="FinalPrice"]',
  '[class*="priceCard"]',
  'span[class*="Price"]',
];

const ORIGINAL_PRICE_SELECTORS = [
  '[data-testid="product-old-price"]',
  '[class*="oldPrice"]',
  '[class*="OldPrice"]',
  'del span',
];

const TITLE_SELECTORS = [
  '[data-testid="product-name"]',
  'h1[class*="Product"]',
  'h1[class*="Title"]',
  'h1',
];

const IMAGE_SELECTORS = [
  '[data-testid="product-image"] img',
  '[class*="ProductImage"] img',
  '[class*="productImage"] img',
  'img[class*="product"]',
];

const UNAVAILABILITY = ['esgotado', 'indisponível', 'sem estoque'];

// ---------------------------------------------------------------------------
// Shared fetch
// ---------------------------------------------------------------------------

async function fetchHtml(url: string): Promise<string | null> {
  return fetchWithTimeout(
    url,
    getRandomHeaders('kabum'),
    { perRequestMs: 12_000, totalTimeoutMs: 35_000, maxRetries: 3, marketplace: 'kabum' },
  );
}

// ---------------------------------------------------------------------------
// Tipos internos
// ---------------------------------------------------------------------------

type Extracted = {
  price: number; name: string | null; imageUrl: string | null;
  originalPrice: number | null; availability: boolean;
};

// ---------------------------------------------------------------------------
// Estratégias
// ---------------------------------------------------------------------------

async function strategyNextData(url: string): Promise<Extracted | null> {
  await humanDelay(200, 800);
  const html = await fetchHtml(url);
  if (html && detectBlock(html)) return null;
  if (!html) return null;

  const data = parseNextData<any>(html);
  if (!data) return null;

  const pd: any =
    data?.props?.pageProps?.productDetail ??
    data?.props?.pageProps?.product ??
    null;
  if (!pd) return null;

  const price: number | null =
    pd.productPrices?.retail?.price ??
    pd.productPrices?.prime?.price ??
    pd.vlrFinal ??
    pd.price ??
    null;

  if (!price) return null;

  const originalPrice = pd.priceFrom && pd.priceFrom > price ? pd.priceFrom : null;
  const imageUrl = pd.minPhoto
    ? `https://images.kabum.com.br/produtos/fotos/${pd.minPhoto}`
    : pd.thumbnail ?? null;
  const availability = pd.availability !== 0;

  return {
    price: Math.round(price * 100) / 100,
    name: pd.title ?? null,
    imageUrl,
    originalPrice: originalPrice ? Math.round(originalPrice * 100) / 100 : null,
    availability,
  };
}

async function strategyJsonLd(url: string): Promise<Extracted | null> {
  await humanDelay(500, 1200);
  const html = await fetchHtml(url);
  if (!html || detectBlock(html)) return null;

  const block = findProductJsonLd(html);
  if (!block) return null;

  const ex = extractFromProductJsonLd(block);
  if (!ex.price) return null;

  const $ = cheerio.load(html);
  const imageUrl = ex.imageUrl ?? extractImageCSS($);

  return { price: ex.price, name: ex.name, imageUrl, originalPrice: ex.originalPrice, availability: ex.availability };
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

export async function scrapeKabum(url: string): Promise<ScrapedProduct> {
  const result = await runStrategies<Extracted>(
    [
      () => strategyNextData(url),
      () => strategyJsonLd(url),
      () => strategyCSS(url),
    ],
    'kabum',
  );

  if (result) return makeProduct({ success: true, store: 'kabum', ...result });
  return makeProduct({ success: false, store: 'kabum', error: 'Todas as estratégias falharam' });
}
