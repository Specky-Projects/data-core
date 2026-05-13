/**
 * ultrafarma.scraper.ts
 *
 * Scraper deterministico para Ultrafarma.
 * A pagina de produto publica JSON-LD Product com offer.price e availability.
 */

import * as cheerio from 'cheerio';
import {
  detectBlock,
  fetchWithTimeout,
  getRandomHeaders,
  makeProduct,
  parsePrice,
  ScrapedProduct,
} from './base.scraper';
import {
  extractFromProductJsonLd,
  findProductJsonLd,
  runStrategies,
} from './strategy';

type Extracted = {
  price: number;
  name: string | null;
  imageUrl: string | null;
  originalPrice: number | null;
  availability: boolean;
};

function fetchHtml(url: string): Promise<string | null> {
  return fetchWithTimeout(
    url,
    getRandomHeaders('ultrafarma'),
    {
      perRequestMs: 12_000,
      totalTimeoutMs: 25_000,
      maxRetries: 2,
      marketplace: 'ultrafarma',
    },
  );
}

async function strategyJsonLd(url: string): Promise<Extracted | null> {
  const html = await fetchHtml(url);
  if (!html || detectBlock(html)) return null;

  const block = findProductJsonLd(html);
  if (!block) return null;

  const extracted = extractFromProductJsonLd(block);
  if (!extracted.price) return null;

  return {
    price: extracted.price,
    name: extracted.name,
    imageUrl: normalizeUrl(url, extracted.imageUrl),
    originalPrice: extractOriginalPrice(html, extracted.price),
    availability: extracted.availability,
  };
}

async function strategyLeanEcommerce(url: string): Promise<Extracted | null> {
  const html = await fetchHtml(url);
  if (!html || detectBlock(html)) return null;

  const price = parsePrice(html.match(/Preco:\s*JSON\.parse\('([\d.]+)'\)/)?.[1])
    ?? parsePrice(html.match(/"ValorTexto":"R\$\s*([\d.,]+)"/)?.[1]);

  if (!price) return null;

  return {
    price,
    name: extractTitle(html),
    imageUrl: extractImage(html, url),
    originalPrice: extractOriginalPrice(html, price),
    availability: !html.includes('product-unavailable'),
  };
}

function extractOriginalPrice(html: string, price: number): number | null {
  const $ = cheerio.load(html);
  const oldPrice = parsePrice($('.product-old-price-info [data-preco]').first().attr('data-preco'))
    ?? parsePrice($('.product-old-price-info').first().text());

  return oldPrice && oldPrice > price ? oldPrice : null;
}

function extractTitle(html: string): string | null {
  const $ = cheerio.load(html);
  const title = $('h1').first().text().replace(/\s+/g, ' ').trim();
  return title || null;
}

function extractImage(html: string, pageUrl: string): string | null {
  const $ = cheerio.load(html);
  const image = $('meta[property="og:image"]').attr('content')
    ?? $('.product-image img').first().attr('src')
    ?? null;

  return normalizeUrl(pageUrl, image);
}

function normalizeUrl(pageUrl: string, value: string | null): string | null {
  if (!value) return null;
  try {
    return new URL(value, new URL(pageUrl).origin).toString();
  } catch {
    return value;
  }
}

export async function scrapeUltrafarma(url: string): Promise<ScrapedProduct> {
  const result = await runStrategies<Extracted>(
    [
      () => strategyJsonLd(url),
      () => strategyLeanEcommerce(url),
    ],
    'ultrafarma',
  );

  if (result) return makeProduct({ success: true, store: 'ultrafarma', ...result });
  return makeProduct({ success: false, store: 'ultrafarma', error: 'Todas as estrategias falharam' });
}
