import {
  fetchWithTimeout,
  getRandomHeaders,
  makeProduct,
  ScrapedProduct,
  ScrapedRegionalOffer,
} from './base.scraper';

type ProductPayload = {
  gtin?: string;
  sku?: string;
  productID?: string;
  name?: string;
  image?: Array<{ url?: string }>;
  categoryProperty?: Array<{ value?: string; categorytype?: boolean }>;
};

type ProductOfferPayload = {
  name?: string;
  formattedSellerName?: string;
  sellerId?: string;
  productID?: string;
  price?: number;
  listPrice?: number;
  inventory?: number;
};

function fetchHtml(url: string): Promise<string | null> {
  return fetchWithTimeout(
    url,
    getRandomHeaders('consultaremedios'),
    { perRequestMs: 12_000, totalTimeoutMs: 25_000, maxRetries: 2, marketplace: 'consultaremedios' },
  );
}

function decodeHtml(text: string): string {
  return text
    .replace(/&quot;/g, '"')
    .replace(/&amp;/g, '&')
    .replace(/&#x27;/g, "'")
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>');
}

function extractJsonValue(text: string, key: string, open: '[' | '{', close: ']' | '}'): string | null {
  const keyIndex = text.indexOf(`"${key}":${open}`);
  if (keyIndex < 0) return null;

  const start = text.indexOf(open, keyIndex);
  let depth = 0;
  let inString = false;
  let escaped = false;

  for (let i = start; i < text.length; i++) {
    const ch = text[i];
    if (escaped) {
      escaped = false;
      continue;
    }
    if (ch === '\\') {
      escaped = true;
      continue;
    }
    if (ch === '"') inString = !inString;
    if (inString) continue;

    if (ch === open) depth++;
    if (ch === close) {
      depth--;
      if (depth === 0) return text.slice(start, i + 1);
    }
  }

  return null;
}

function sellerSlug(name: string): string {
  return name
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '')
    .slice(0, 80);
}

export async function scrapeConsultaRemedios(url: string): Promise<ScrapedProduct> {
  const html = await fetchHtml(url);
  if (!html) return makeProduct({ success: false, store: 'consultaremedios', error: 'HTML indisponivel' });

  const decoded = decodeHtml(html);
  const offersText = extractJsonValue(decoded, 'productOffers', '[', ']');
  const productText = extractJsonValue(decoded, 'product', '{', '}');
  if (!offersText || !productText) {
    return makeProduct({ success: false, store: 'consultaremedios', error: 'Bloco productOffers nao encontrado' });
  }

  const offers = JSON.parse(offersText) as ProductOfferPayload[];
  const product = JSON.parse(productText) as ProductPayload;

  const regionalOffers: ScrapedRegionalOffer[] = offers
    .filter((offer) => offer.price && offer.price > 0 && (offer.sellerId || offer.formattedSellerName || offer.name))
    .map((offer) => {
      const marketplaceName = offer.formattedSellerName ?? offer.name ?? offer.sellerId ?? 'Consulta Remedios';
      const marketplaceSlug = sellerSlug(offer.sellerId && offer.sellerId !== '1' ? offer.sellerId : marketplaceName);
      return {
        marketplaceName,
        marketplaceSlug,
        externalId: `CR-${product.productID ?? product.sku ?? 'product'}-${offer.sellerId ?? marketplaceSlug}`,
        url: `${url}${url.includes('?') ? '&' : '?'}sellerId=${encodeURIComponent(offer.sellerId ?? marketplaceSlug)}`,
        currentPrice: offer.price as number,
        originalPrice: offer.listPrice && offer.listPrice > (offer.price ?? 0) ? offer.listPrice : null,
        stock: offer.inventory ?? null,
        availability: (offer.inventory ?? 0) > 0,
      };
    })
    .sort((a, b) => a.currentPrice - b.currentPrice);

  const bestOffer = regionalOffers[0];
  if (!bestOffer) {
    return makeProduct({ success: false, store: 'consultaremedios', error: 'Nenhuma oferta valida encontrada' });
  }

  const category = product.categoryProperty?.find((item) => item.categorytype)?.value
    ?? product.categoryProperty?.find((item) => item.value)?.value
    ?? null;

  return makeProduct({
    success: true,
    store: 'consultaremedios',
    price: bestOffer.currentPrice,
    originalPrice: bestOffer.originalPrice,
    name: product.name ?? null,
    imageUrl: product.image?.find((image) => image.url)?.url ?? null,
    availability: true,
    regionalOffers,
    ean: product.gtin ?? product.sku ?? null,
    category,
  });
}
