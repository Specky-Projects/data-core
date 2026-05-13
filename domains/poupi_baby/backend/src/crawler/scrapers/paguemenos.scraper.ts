/**
 * paguemenos.scraper.ts
 *
 * Scraper deterministico para Pague Menos.
 *
 * Estrategias:
 *   1. JSON-LD Product
 *   2. CSS selectors comuns de produto
 *   3. Regex no HTML como fallback restrito
 */

import * as cheerio from 'cheerio';
import {
  detectBlock,
  fetchWithTimeout,
  getRandomHeaders,
  humanDelay,
  makeProduct,
  parsePrice,
  ScrapedProduct,
} from './base.scraper';
import {
  extractFromProductJsonLd,
  findProductJsonLd,
  runStrategies,
} from './strategy';

const PRICE_SELECTORS = [
  "[data-testid*='price']",
  "[class*='sellingPrice']",
  "[class*='salePrice']",
  "[class*='price']",
  "[class*='preco']",
  "[itemprop='price']",
];

const ORIGINAL_PRICE_SELECTORS = [
  "[class*='listPrice']",
  "[class*='oldPrice']",
  "[class*='originalPrice']",
  'del',
  's',
];

const TITLE_SELECTORS = [
  'h1',
  "[data-testid*='title']",
  "[class*='productName']",
  "[class*='ProductName']",
  "[itemprop='name']",
];

const IMAGE_SELECTORS = [
  "[data-testid*='image'] img",
  "[class*='productImage'] img",
  "[class*='ProductImage'] img",
  "[itemprop='image']",
  'main img',
];

const UNAVAILABILITY = [
  'produto indisponivel',
  'esgotado',
  'sem estoque',
  'fora de estoque',
  'indisponivel',
];

type Extracted = {
  price: number;
  name: string | null;
  imageUrl: string | null;
  originalPrice: number | null;
  availability: boolean;
};

type VtexProduct = {
  productName?: string;
  productTitle?: string;
  items?: Array<{
    name?: string;
    images?: Array<{ imageUrl?: string }>;
    sellers?: Array<{
      commertialOffer?: {
        Price?: number;
        ListPrice?: number;
        AvailableQuantity?: number;
        IsAvailable?: boolean;
      };
    }>;
  }>;
};

function apiUrlFromProductUrl(url: string): string | null {
  try {
    const parsed = new URL(url);
    const slug = parsed.pathname.replace(/^\/+/, '').replace(/\/+$/, '');
    if (!slug) return null;
    return `${parsed.origin}/api/catalog_system/pub/products/search/${slug}`;
  } catch {
    return null;
  }
}

function fetchHtml(url: string): Promise<string | null> {
  return fetchWithTimeout(
    url,
    getRandomHeaders('paguemenos'),
    {
      perRequestMs: 12_000,
      totalTimeoutMs: 35_000,
      maxRetries: 3,
      marketplace: 'paguemenos',
    },
  );
}

async function strategyCatalogApi(url: string): Promise<Extracted | null> {
  const apiUrl = apiUrlFromProductUrl(url);
  if (!apiUrl) return null;

  const response = await fetch(apiUrl, {
    headers: {
      ...getRandomHeaders('paguemenos'),
      Accept: 'application/json,text/plain,*/*',
    },
  });
  if (!response.ok) return null;

  const products = await response.json().catch(() => null) as VtexProduct[] | null;
  const product = Array.isArray(products) ? products[0] : null;
  if (!product) return null;

  const offers = (product.items ?? [])
    .flatMap((item) => (item.sellers ?? []).map((seller) => ({
      item,
      offer: seller.commertialOffer,
    })))
    .filter((entry) => typeof entry.offer?.Price === 'number' && entry.offer.Price > 0);

  const selected = offers
    .sort((a, b) => (a.offer?.Price ?? Number.MAX_VALUE) - (b.offer?.Price ?? Number.MAX_VALUE))[0];
  if (!selected?.offer?.Price) return null;

  const listPrice = selected.offer.ListPrice ?? null;
  return {
    price: selected.offer.Price,
    name: product.productName ?? product.productTitle ?? selected.item.name ?? null,
    imageUrl: selected.item.images?.find((image) => image.imageUrl)?.imageUrl ?? null,
    originalPrice: listPrice && listPrice > selected.offer.Price ? listPrice : null,
    availability: Boolean(selected.offer.IsAvailable ?? ((selected.offer.AvailableQuantity ?? 0) > 0)),
  };
}

async function strategyJsonLd(url: string): Promise<Extracted | null> {
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
    availability: ex.availability && checkAvailability($),
  };
}

async function strategyCSS(url: string): Promise<Extracted | null> {
  await humanDelay(500, 1400);
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
    availability: checkAvailability($),
  };
}

async function strategyRegex(url: string): Promise<Extracted | null> {
  await humanDelay(800, 2000);
  const html = await fetchHtml(url);
  if (!html || detectBlock(html)) return null;

  const patterns = [
    /"price"\s*:\s*"?([\d.,]+)"?/,
    /"sellingPrice"\s*:\s*"?([\d.,]+)"?/,
    /R\$\s*([\d.]+,\d{2})/,
  ];

  for (const pattern of patterns) {
    const match = html.match(pattern);
    const price = match ? parsePrice(match[1]) : null;
    if (price) {
      return {
        price,
        name: null,
        imageUrl: null,
        originalPrice: null,
        availability: true,
      };
    }
  }

  return null;
}

function extractPriceCSS($: cheerio.CheerioAPI): number | null {
  for (const selector of PRICE_SELECTORS) {
    const value =
      $(selector).first().attr('content') ??
      $(selector).first().text().trim();
    const price = parsePrice(value);
    if (price) return price;
  }
  return null;
}

function extractOriginalPriceCSS($: cheerio.CheerioAPI): number | null {
  for (const selector of ORIGINAL_PRICE_SELECTORS) {
    const price = parsePrice($(selector).first().text().trim());
    if (price) return price;
  }
  return null;
}

function extractTitleCSS($: cheerio.CheerioAPI): string | null {
  for (const selector of TITLE_SELECTORS) {
    const text = $(selector).first().text().trim().replace(/\s+/g, ' ');
    if (text && text.length > 3) return text;
  }
  return null;
}

function extractImageCSS($: cheerio.CheerioAPI): string | null {
  for (const selector of IMAGE_SELECTORS) {
    const element = $(selector).first();
    const src =
      element.attr('src') ??
      element.attr('data-src') ??
      element.attr('content');

    if (src && !src.startsWith('data:')) return src;
  }
  return null;
}

function checkAvailability($: cheerio.CheerioAPI): boolean {
  const body = normalizeText($('body').text());
  return !UNAVAILABILITY.some((keyword) => body.includes(keyword));
}

function normalizeText(text: string): string {
  return text
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase();
}

export async function scrapePagueMenos(url: string): Promise<ScrapedProduct> {
  const result = await runStrategies<Extracted>(
    [
      () => strategyCatalogApi(url),
      () => strategyJsonLd(url),
      () => strategyCSS(url),
      () => strategyRegex(url),
    ],
    'paguemenos',
  );

  if (result) return makeProduct({ success: true, store: 'paguemenos', ...result });
  return makeProduct({ success: false, store: 'paguemenos', error: 'Todas as estrategias falharam' });
}
