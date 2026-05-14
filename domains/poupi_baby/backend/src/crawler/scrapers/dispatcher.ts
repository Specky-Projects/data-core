/**
 * dispatcher.ts
 *
 * Ponto de entrada único para scraping.
 * Toda a lógica de "qual scraper usar" vive em registry.ts.
 *
 * Fluxo:
 *   URL → detectMarketplace() → scraper correto → ScrapedProduct
 *                                     ↓ não encontrado
 *                               genericScraper (fallback)
 */

import * as cheerio from 'cheerio';
import {
  fetchWithTimeout,
  getRandomHeaders,
  makeProduct,
  parsePrice,
  ScrapedProduct,
} from './base.scraper';
import { detectMarketplace, detectStoreName, ScraperEntry, SCRAPERS } from './registry';

// ---------------------------------------------------------------------------
// Scraper genérico — fallback para lojas sem scraper dedicado
// ---------------------------------------------------------------------------

const GENERIC_PRICE_SELECTORS = [
  "[itemprop='price']",
  "[class*='price']",
  "[class*='valor']",
  "[class*='preco']",
  '.product-price',
  '.offer-price',
];

const GENERIC_TITLE_SELECTORS = ['h1', "[itemprop='name']", '.product-title'];

async function genericScraper(url: string, store: string): Promise<ScrapedProduct> {
  const html = await fetchWithTimeout(url, getRandomHeaders(), { totalTimeoutMs: 20_000 });

  if (!html) {
    return makeProduct({ success: false, store, error: 'Falha ao buscar página' });
  }

  const $ = cheerio.load(html);

  let price: number | null = null;
  for (const sel of GENERIC_PRICE_SELECTORS) {
    price = parsePrice($(sel).first().text().trim());
    if (price) break;
  }
  if (!price) {
    const match = $.html().match(/R\$\s*([\d.]+,\d{2})/);
    if (match) price = parsePrice(match[1]);
  }

  let name: string | null = null;
  for (const sel of GENERIC_TITLE_SELECTORS) {
    const text = $(sel).first().text().trim().replace(/\s+/g, ' ');
    if (text && text.length > 3) { name = text; break; }
  }

  const imageUrl =
    $("[itemprop='image']").attr('src') ??
    $('img.product-image, img.main-image').first().attr('src') ??
    null;

  if (!price) return makeProduct({ success: false, store, name, error: 'Preço não encontrado' });
  return makeProduct({ success: true, store, price, name, imageUrl });
}

// ---------------------------------------------------------------------------
// API pública
// ---------------------------------------------------------------------------

/**
 * Detecta o marketplace e executa o scraper correto.
 * Alias de compatibilidade — mantém a assinatura antiga.
 *
 * @deprecated Use scrapeProduct() direto; store é detectado automaticamente.
 */
export function detectStore(url: string): string | null {
  return detectStoreName(url);
}

/**
 * Scraping principal.
 *
 * @param url   URL do produto
 * @param store Opcional — forçar loja específica pelo nome (ignora detecção)
 */
export async function scrapeProduct(url: string, store?: string): Promise<ScrapedProduct> {
  let entry: ScraperEntry | null = null;

  if (store) {
    // Busca pelo nome forçado
    entry = SCRAPERS.find((s) => s.name === store) ?? null;
  } else {
    entry = detectMarketplace(url);
  }

  if (entry) {
    return entry.scraper(url);
  }

  // Fallback genérico
  const label = store ?? detectStoreName(url) ?? new URL(url).hostname;
  return genericScraper(url, label);
}
