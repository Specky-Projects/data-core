import {
  getRandomHeaders,
  makeProduct,
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

type VtexProduct = {
  productName?: string;
  productTitle?: string;
  brand?: string;
  categories?: string[];
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

async function strategyCatalogApi(url: string): Promise<Extracted | null> {
  const apiUrl = apiUrlFromProductUrl(url);
  if (!apiUrl) return null;

  const response = await fetch(apiUrl, {
    headers: {
      ...getRandomHeaders('farma22'),
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
  const category = product.categories?.find((item) => item.includes('/Mae e Bebe/') || item.includes('/Mãe e Bebê/')) ?? null;

  return {
    price: selected.offer.Price,
    name: product.productTitle ?? product.productName ?? selected.item.name ?? null,
    imageUrl: selected.item.images?.find((image) => image.imageUrl)?.imageUrl ?? null,
    originalPrice: listPrice && listPrice > selected.offer.Price ? listPrice : null,
    availability: Boolean(selected.offer.IsAvailable ?? ((selected.offer.AvailableQuantity ?? 0) > 0)),
    category,
  };
}

export async function scrapeFarma22(url: string): Promise<ScrapedProduct> {
  const result = await runStrategies<Extracted>(
    [
      () => strategyCatalogApi(url),
    ],
    'farma22',
  );

  if (result) return makeProduct({ success: true, store: 'farma22', ...result });
  return makeProduct({ success: false, store: 'farma22', error: 'API publica VTEX nao retornou preco valido' });
}
