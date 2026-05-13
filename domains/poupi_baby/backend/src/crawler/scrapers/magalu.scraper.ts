/**
 * magalu.scraper.ts
 *
 * Estratégias (em ordem):
 *   1. __NEXT_DATA__ JSON
 *   2. JSON-LD Product
 *   3. CSS selectors (data-testid do design system Magalu)
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
  '[data-testid="price-value"]',
  '[class*="Price__value"]',
  '[class*="priceValue"]',
  'p[class*="price"]',
  '.price-template__text',
  '[class*="sc-kpDqfm"]',
];

const ORIGINAL_PRICE_SELECTORS = [
  '[data-testid="price-original"]',
  '[class*="originalPrice"]',
  's[class*="price"]',
  '.price-template__text--original',
];

const TITLE_SELECTORS = [
  '[data-testid="heading-product-title"]',
  'h1[class*="Title"]',
  'h1[class*="title"]',
  'h1',
];

const IMAGE_SELECTORS = [
  '[data-testid="image-selected-thumbnail"] img',
  '[class*="ProductPhoto"] img',
  '[class*="productPhoto"] img',
  'figure img',
];

const UNAVAILABILITY = ['esgotado', 'indisponível', 'produto indisponível', 'sem estoque'];

// ---------------------------------------------------------------------------
// Shared fetch
// ---------------------------------------------------------------------------

async function fetchHtml(url: string): Promise<string | null> {
  return fetchWithTimeout(
    url,
    getRandomHeaders('magalu'),
    { perRequestMs: 12_000, totalTimeoutMs: 35_000, maxRetries: 3, marketplace: 'magalu' },
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
  if (!html || detectBlock(html)) return null;

  const data = parseNextData<any>(html);
  if (!data) return null;

  const pp = data?.props?.pageProps;
  const prod: any = pp?.data?.product ?? pp?.product ?? null;
  if (!prod) return null;

  const price: number | null =
    prod.price?.bestPrice ??
    prod.price ??
    null;
  if (!price) return null;

  const originalPrice: number | null =
    (prod.price?.originalPrice ?? prod.originalPrice ?? null);

  const images: any[] = prod.image?.sources ?? prod.images ?? [];
  const imageUrl: string | null = images[0]?.url ?? null;

  const avail: string = prod.availability?.status ?? '';
  const availability = avail !== 'out_of_stock' && avail !== 'unavailable';

  return {
    price: Math.round(price * 100) / 100,
    name: prod.title ?? null,
    imageUrl,
    originalPrice: originalPrice && originalPrice > price ? Math.round(originalPrice * 100) / 100 : null,
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
  return { price: ex.price, name: ex.name, imageUrl: ex.imageUrl ?? extractImageCSS($), originalPrice: ex.originalPrice, availability: ex.availability };
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

export async function scrapeMagalu(url: string): Promise<ScrapedProduct> {
  const result = await runStrategies<Extracted>(
    [
      () => strategyNextData(url),
      () => strategyJsonLd(url),
      () => strategyCSS(url),
    ],
    'magalu',
  );

  if (result) return makeProduct({ success: true, store: 'magalu', ...result });
  return makeProduct({ success: false, store: 'magalu', error: 'Todas as estratégias falharam' });
}
