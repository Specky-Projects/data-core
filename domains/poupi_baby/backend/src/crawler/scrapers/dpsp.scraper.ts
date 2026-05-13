/**
 * dpsp.scraper.ts
 *
 * Scraper para Drogarias Pacheco e Drogaria Sao Paulo.
 * As lojas usam VTEX legado e expõem dados confiáveis pela API pública
 * /api/catalog_system/pub/products/search/{slug}.
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
import { runStrategies } from './strategy';

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
    itemId?: string;
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

function storeFromUrl(url: string): 'drogariaspacheco' | 'drogariasaopaulo' {
  return url.includes('drogariaspacheco') ? 'drogariaspacheco' : 'drogariasaopaulo';
}

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

async function strategyCatalogApi(url: string): Promise<Extracted | null> {
  const apiUrl = apiUrlFromProductUrl(url);
  if (!apiUrl) return null;

  const store = storeFromUrl(url);
  const response = await fetch(apiUrl, {
    headers: {
      ...getRandomHeaders(store),
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

async function strategySkuJson(url: string): Promise<Extracted | null> {
  const store = storeFromUrl(url);
  const html = await fetchWithTimeout(
    url,
    getRandomHeaders(store),
    {
      perRequestMs: 12_000,
      totalTimeoutMs: 25_000,
      maxRetries: 2,
      marketplace: store,
    },
  );
  if (!html || detectBlock(html)) return null;

  const match = html.match(/var\s+skuJson(?:_\d+)?\s*=\s*(\{[\s\S]*?\});/);
  if (!match) return null;

  try {
    const skuJson = JSON.parse(match[1]) as {
      name?: string;
      available?: boolean;
      skus?: Array<{
        skuname?: string;
        available?: boolean;
        availablequantity?: number;
        bestPrice?: number;
        spotPrice?: number;
        listPrice?: number;
        image?: string;
      }>;
    };

    const sku = skuJson.skus?.find((entry) => entry.available) ?? skuJson.skus?.[0];
    const cents = sku?.spotPrice ?? sku?.bestPrice ?? null;
    if (!cents) return null;

    const price = Math.round((cents / 100) * 100) / 100;
    const originalPrice = sku?.listPrice && sku.listPrice > cents
      ? Math.round((sku.listPrice / 100) * 100) / 100
      : null;

    return {
      price,
      name: skuJson.name ?? sku?.skuname ?? null,
      imageUrl: sku?.image ?? extractImage(html),
      originalPrice,
      availability: Boolean(skuJson.available ?? sku?.available ?? ((sku?.availablequantity ?? 0) > 0)),
    };
  } catch {
    return null;
  }
}

function extractImage(html: string): string | null {
  const $ = cheerio.load(html);
  return $('meta[property="og:image"]').attr('content')
    ?? $('.image-zoom').first().attr('src')
    ?? null;
}

export async function scrapeDpsp(url: string): Promise<ScrapedProduct> {
  const store = storeFromUrl(url);
  const result = await runStrategies<Extracted>(
    [
      () => strategyCatalogApi(url),
      () => strategySkuJson(url),
    ],
    store,
  );

  if (result) return makeProduct({ success: true, store, ...result });
  return makeProduct({ success: false, store, error: 'Todas as estrategias falharam' });
}
