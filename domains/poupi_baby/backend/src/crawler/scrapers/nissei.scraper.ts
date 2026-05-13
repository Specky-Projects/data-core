/**
 * nissei.scraper.ts
 *
 * Scraper deterministico para Farmacias Nissei.
 *
 * A pagina publica JSON-LD de Product com sku, imagem e offer.price. O fallback
 * fica restrito ao price_datalayer para evitar capturar precos de vitrine,
 * carrinho ou "compre junto".
 */

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
    getRandomHeaders('nissei'),
    {
      perRequestMs: 12_000,
      totalTimeoutMs: 25_000,
      maxRetries: 2,
      marketplace: 'nissei',
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
    originalPrice: extracted.originalPrice,
    availability: extracted.availability,
  };
}

async function strategyDataLayer(url: string): Promise<Extracted | null> {
  const html = await fetchHtml(url);
  if (!html || detectBlock(html)) return null;

  const price = parsePrice(html.match(/price_datalayer\s*=\s*["']([\d.]+)["']/)?.[1]);
  const name = html
    .match(/<h1[^>]*data-target=["']nome_produto["'][^>]*>([\s\S]*?)<\/h1>/i)?.[1]
    ?.replace(/<[^>]+>/g, '')
    .replace(/\s+/g, ' ')
    .trim() ?? null;
  const imageUrl = html.match(/<meta\s+property=["']og:image["']\s+content=["']([^"']+)["']/i)?.[1] ?? null;

  if (!price) return null;

  return {
    price,
    name,
    imageUrl: normalizeUrl(url, imageUrl),
    originalPrice: null,
    availability: true,
  };
}

function normalizeUrl(pageUrl: string, value: string | null): string | null {
  if (!value) return null;
  try {
    return new URL(value, new URL(pageUrl).origin).toString();
  } catch {
    return value;
  }
}

export async function scrapeNissei(url: string): Promise<ScrapedProduct> {
  const result = await runStrategies<Extracted>(
    [
      () => strategyJsonLd(url),
      () => strategyDataLayer(url),
    ],
    'nissei',
  );

  if (result) return makeProduct({ success: true, store: 'nissei', ...result });
  return makeProduct({ success: false, store: 'nissei', error: 'Todas as estrategias falharam' });
}
