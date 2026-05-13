/**
 * registry.ts
 *
 * Registro central de marketplaces.
 *
 * Para adicionar uma nova loja:
 *   1. Crie <loja>.scraper.ts exportando scraperFn: (url: string) => Promise<ScrapedProduct>
 *   2. Adicione uma entrada aqui com match: ['dominio.com.br']
 *   Só isso. O dispatcher e o detector usam este arquivo automaticamente.
 */

import { ScrapedProduct } from './base.scraper';
import { scrapeAmazon } from './amazon.scraper';
import { scrapeMercadoLivre } from './mercadolivre.scraper';
import { scrapeKabum } from './kabum.scraper';
import { scrapeMagalu } from './magalu.scraper';
import { scrapeDrogasil } from './drogasil.scraper';
import { scrapePagueMenos } from './paguemenos.scraper';
import { scrapeNissei } from './nissei.scraper';
import { scrapeUltrafarma } from './ultrafarma.scraper';
import { scrapeDpsp } from './dpsp.scraper';
import { scrapeConsultaRemedios } from './consultaremedios.scraper';
import { scrapeFarma22 } from './farma22.scraper';
import { scrapePanvel } from './panvel.scraper';

// ---------------------------------------------------------------------------
// Tipos
// ---------------------------------------------------------------------------

export type ScraperFn = (url: string) => Promise<ScrapedProduct>;

export interface ScraperEntry {
  /** Nome legível da loja (usado em logs e no campo store do resultado) */
  name: string;
  /** Substrings de hostname que identificam este marketplace */
  match: string[];
  /** Função de scraping */
  scraper: ScraperFn;
}

// ---------------------------------------------------------------------------
// Registro
// ---------------------------------------------------------------------------

export const SCRAPERS: ScraperEntry[] = [
  {
    name: 'amazon',
    match: ['amazon.com.br', 'amazon.com', 'amzn.to'],
    scraper: scrapeAmazon,
  },
  {
    name: 'mercadolivre',
    match: ['mercadolivre.com.br', 'produto.mercadolivre.com.br', 'mercadolibre.com'],
    scraper: scrapeMercadoLivre,
  },
  {
    name: 'kabum',
    match: ['kabum.com.br'],
    scraper: scrapeKabum,
  },
  {
    name: 'magalu',
    match: ['magazineluiza.com.br', 'magalu.com'],
    scraper: scrapeMagalu,
  },
  {
    name: 'drogasil',
    match: ['drogasil.com.br'],
    scraper: scrapeDrogasil,
  },
  {
    name: 'drogaraia',
    match: ['drogaraia.com.br'],
    scraper: scrapeDrogasil,
  },
  {
    name: 'paguemenos',
    match: ['paguemenos.com.br'],
    scraper: scrapePagueMenos,
  },
  {
    name: 'nissei',
    match: ['farmaciasnissei.com.br'],
    scraper: scrapeNissei,
  },
  {
    name: 'ultrafarma',
    match: ['ultrafarma.com.br'],
    scraper: scrapeUltrafarma,
  },
  {
    name: 'drogariaspacheco',
    match: ['drogariaspacheco.com.br'],
    scraper: scrapeDpsp,
  },
  {
    name: 'drogariasaopaulo',
    match: ['drogariasaopaulo.com.br'],
    scraper: scrapeDpsp,
  },
  {
    name: 'consultaremedios',
    match: ['consultaremedios.com.br'],
    scraper: scrapeConsultaRemedios,
  },
  {
    name: 'farma22',
    match: ['farma22.com.br'],
    scraper: scrapeFarma22,
  },
  {
    name: 'panvel',
    match: ['panvel.com'],
    scraper: scrapePanvel,
  },
  // ──────────────────────────────────────────────────────────────────────────
  // Próximas lojas a implementar:
  // { name: 'americanas',  match: ['americanas.com.br'],  scraper: scrapeAmericanas  },
  // { name: 'shopee',      match: ['shopee.com.br'],       scraper: scrapeShopee      },
  // { name: 'casasbahia',  match: ['casasbahia.com.br'],   scraper: scrapeCasasBahia  },
  // { name: 'carrefour',   match: ['carrefour.com.br'],    scraper: scrapeCarrefour   },
  // ──────────────────────────────────────────────────────────────────────────
];

// ---------------------------------------------------------------------------
// Detecção automática
// ---------------------------------------------------------------------------

/**
 * Detecta qual scraper usar para uma URL.
 * Compara o hostname (sem www.) contra os match[] de cada entrada.
 *
 * @returns ScraperEntry encontrada ou null se marketplace não suportado
 */
export function detectMarketplace(url: string): ScraperEntry | null {
  let hostname: string;
  try {
    hostname = new URL(url).hostname.replace(/^www\./, '');
  } catch {
    return null;
  }

  return SCRAPERS.find((entry) =>
    entry.match.some((m) => hostname === m || hostname.endsWith(`.${m}`) || m.includes(hostname)),
  ) ?? null;
}

/**
 * Retorna o nome da loja ou null.
 * Atalho para detectMarketplace(url)?.name.
 */
export function detectStoreName(url: string): string | null {
  return detectMarketplace(url)?.name ?? null;
}

/**
 * Lista todos os hostnames suportados (útil para validação em services).
 */
export function supportedHosts(): string[] {
  return SCRAPERS.flatMap((e) => e.match);
}
