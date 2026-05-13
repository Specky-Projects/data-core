/**
 * amazon.scraper.ts
 *
 * Estratégias (em ordem):
 *   1. JSON-LD  <script type="application/ld+json"> Product
 *   2. CSS selectors (10+ seletores principais)
 *   3. Regex no HTML (último recurso)
 *
 * Mitigações de bot-detection:
 *   - User-Agent rotativo + Headers realistas
 *   - Detecção de CAPTCHA com falha explícita
 *   - fetchWithTimeout: Promise.race() — deadline absoluto
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
// Seletores CSS
// ---------------------------------------------------------------------------

const PRICE_SELECTORS = [
  '.a-price.aok-align-center.reinventPricePriceToPayMargin .a-offscreen',
  '.a-price .a-offscreen',
  '#priceblock_ourprice',
  '#priceblock_dealprice',
  '#priceblock_saleprice',
  '.a-price-whole',
  '#price_inside_buybox',
  '#newBuyBoxPrice',
  '.a-color-price',
  "[data-feature-name='priceInsideBuyBox'] .a-price .a-offscreen",
];

const ORIGINAL_PRICE_SELECTORS = [
  '.a-price.a-text-price .a-offscreen',
  '.basisPrice .a-offscreen',
  '.a-text-strike',
];

const TITLE_SELECTORS = [
  '#productTitle',
  '#title',
  'h1.a-size-large',
  "h1[data-cel-widget='title'] span",
];

const IMAGE_SELECTORS = [
  '#landingImage',
  '#imgBlkFront',
  '#ebooksImgBlkFront',
  '.a-dynamic-image.a-stretch-vertical',
];

const UNAVAILABILITY_KEYWORDS = [
  'atualmente indisponível', 'currently unavailable',
  'não disponível', 'esgotado', 'out of stock', 'fora de estoque',
];

const CAPTCHA_INDICATORS = [
  'Insira os caracteres que você vê abaixo',
  'Type the characters you see in this image',
  'captcha', 'robot check', 'automated access',
];

// ---------------------------------------------------------------------------
// Shared fetch (singleton por chamada)
// ---------------------------------------------------------------------------

async function fetchHtml(url: string): Promise<string | null> {
  return fetchWithTimeout(
    url,
    getRandomHeaders('amazon'),
    { perRequestMs: 12_000, totalTimeoutMs: 35_000, maxRetries: 3, marketplace: 'amazon' },
  );
}

// ---------------------------------------------------------------------------
// Estratégias individuais
// ---------------------------------------------------------------------------

type Extracted = {
  price: number; name: string | null; imageUrl: string | null;
  originalPrice: number | null; availability: boolean;
};

async function strategyJsonLd(url: string): Promise<Extracted | null> {
  const html = await fetchHtml(url);
  if (!html) return null;

  const block = findProductJsonLd(html);
  if (!block) return null;

  const ex = extractFromProductJsonLd(block);
  if (!ex.price) return null;

  // Enriquecer imagem via CSS se JSON-LD não trouxer
  const $ = cheerio.load(html);
  const imageUrl = ex.imageUrl ?? extractImageCSS($);

  return { price: ex.price, name: ex.name, imageUrl, originalPrice: ex.originalPrice, availability: ex.availability };
}

async function strategyCSS(url: string): Promise<Extracted | null> {
  await humanDelay(500, 1500);
  const html = await fetchHtml(url);
  if (!html) return null;

  if (detectBlock(html)) return null;
  const lower = html.toLowerCase();
  if (CAPTCHA_INDICATORS.some((c) => lower.includes(c.toLowerCase()))) return null;

  const $ = cheerio.load(html);
  const price = extractPriceCSS($);
  if (!price) return null;

  return {
    price,
    name: extractTitleCSS($),
    imageUrl: extractImageCSS($),
    originalPrice: extractOriginalPriceCSS($),
    availability: checkAvailability($),
  };
}

async function strategyRegex(url: string): Promise<Extracted | null> {
  await humanDelay(800, 2000);
  const html = await fetchHtml(url);
  if (!html) return null;

  const patterns = [
    /"priceAmount"\s*:\s*"?([\d.,]+)"?/,
    /R\$\s*([\d.]+,\d{2})/,
    /"buyingPrice"\s*:\s*([\d.]+)/,
  ];

  for (const pattern of patterns) {
    const match = html.match(pattern);
    const price = match ? parsePrice(match[1]) : null;
    if (price) return { price, name: null, imageUrl: null, originalPrice: null, availability: true };
  }

  return null;
}

// ---------------------------------------------------------------------------
// Extratores CSS
// ---------------------------------------------------------------------------

function extractPriceCSS($: cheerio.CheerioAPI): number | null {
  for (const sel of PRICE_SELECTORS) {
    const price = parsePrice($(sel).first().text().trim());
    if (price) return price;
  }
  return null;
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
    if (text) return text;
  }
  return null;
}

function extractImageCSS($: cheerio.CheerioAPI): string | null {
  for (const sel of IMAGE_SELECTORS) {
    const el = $(sel).first();
    const hires = el.attr('data-old-hires');
    if (hires) return hires;
    const dynamicRaw = el.attr('data-a-dynamic-image');
    if (dynamicRaw) {
      try {
        const urls = Object.keys(JSON.parse(dynamicRaw));
        if (urls.length) return urls[urls.length - 1];
      } catch { /* ignora */ }
    }
    const src = el.attr('src');
    if (src && !src.includes('data:')) return src;
  }
  return null;
}

function checkAvailability($: cheerio.CheerioAPI): boolean {
  const availText = $('#availability').text().toLowerCase();
  return !UNAVAILABILITY_KEYWORDS.some((kw) => availText.includes(kw));
}

// ---------------------------------------------------------------------------
// Função principal
// ---------------------------------------------------------------------------

export async function scrapeAmazon(url: string): Promise<ScrapedProduct> {
  const result = await runStrategies<Extracted>(
    [
      () => strategyJsonLd(url),
      () => strategyCSS(url),
      () => strategyRegex(url),
    ],
    'amazon',
  );

  if (result) {
    return makeProduct({ success: true, store: 'amazon', ...result });
  }

  return makeProduct({ success: false, store: 'amazon', error: 'Todas as estratégias falharam' });
}
