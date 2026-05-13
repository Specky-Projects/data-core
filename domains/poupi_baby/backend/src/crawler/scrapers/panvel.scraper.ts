import {
  detectBlock,
  fetchWithTimeout,
  getRandomHeaders,
  makeProduct,
  parsePrice,
  ScrapedProduct,
} from './base.scraper';
import { runStrategies } from './strategy';

type Extracted = {
  price: number;
  name: string | null;
  imageUrl: string | null;
  originalPrice: number | null;
  availability: boolean;
  category?: string | null;
};

type PanvelProduct = {
  name?: string;
  stockStatus?: string;
  price?: number | string;
  originalPrice?: number | string;
  listPrice?: number | string;
  salePrice?: number | string;
  images?: Array<{ url?: string }>;
  tags?: Array<{ description?: string }>;
};

function extractProductId(url: string): string | null {
  const match = url.match(/p-(\d+)/i);
  return match?.[1] ?? null;
}

function extractNgState(html: string): Record<string, unknown> | null {
  const match = html.match(/<script[^>]*id="ng-state"[^>]*type="application\/json"[^>]*>([\s\S]*?)<\/script>/i);
  if (!match) return null;
  try {
    return JSON.parse(match[1]) as Record<string, unknown>;
  } catch {
    return null;
  }
}

function findPanvelProduct(state: Record<string, unknown>, productId: string): PanvelProduct | null {
  const exact = state[`api/v2/catalog/${productId}?type=SSR`] as PanvelProduct | undefined;
  const wrapped = state[`G.json.api/v2/catalog/${productId}?type=SSR`] as { body?: PanvelProduct } | undefined;
  return exact ?? wrapped?.body ?? null;
}

async function strategySsr(url: string): Promise<Extracted | null> {
  const productId = extractProductId(url);
  if (!productId) return null;

  const html = await fetchWithTimeout(
    url,
    getRandomHeaders('panvel'),
    {
      perRequestMs: 12_000,
      totalTimeoutMs: 30_000,
      maxRetries: 2,
      marketplace: 'panvel',
    },
  );
  if (!html || detectBlock(html)) return null;

  const state = extractNgState(html);
  const product = state ? findPanvelProduct(state, productId) : null;
  if (!product) return null;

  const price =
    parsePrice(String(product.price ?? '')) ??
    parsePrice(String(product.salePrice ?? ''));

  if (!price) {
    return null;
  }

  const originalPrice =
    parsePrice(String(product.originalPrice ?? '')) ??
    parsePrice(String(product.listPrice ?? ''));

  return {
    price,
    name: product.name ?? extractMeta(html, 'og:title'),
    imageUrl: product.images?.find((image) => image.url)?.url ?? extractMeta(html, 'og:image'),
    originalPrice: originalPrice && originalPrice > price ? originalPrice : null,
    availability: !String(product.stockStatus ?? '').toLowerCase().includes('unavailable'),
    category: product.tags?.find((tag) => tag.description)?.description ?? null,
  };
}

function extractMeta(html: string, property: string): string | null {
  const escaped = property.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const match = html.match(new RegExp(`<meta[^>]+property=["']${escaped}["'][^>]+content=["']([^"']+)["']`, 'i'));
  return match?.[1] ?? null;
}

export async function scrapePanvel(url: string): Promise<ScrapedProduct> {
  const result = await runStrategies<Extracted>(
    [
      () => strategySsr(url),
    ],
    'panvel',
  );

  if (result) return makeProduct({ success: true, store: 'panvel', ...result });
  return makeProduct({
    success: false,
    store: 'panvel',
    error: 'Panvel retornou dados do produto, mas nao expôs preco no HTML/SSR publico para esta regiao',
  });
}
