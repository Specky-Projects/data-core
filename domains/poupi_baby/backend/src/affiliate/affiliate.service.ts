/**
 * affiliate.service.ts
 *
 * Geração de URLs de afiliado por marketplace e detecção de loja.
 *
 * Suporte atual:
 *   - Amazon Brasil (tag de afiliado)
 *   - Mercado Livre Brasil (UTM + partner_id)
 *   - Genérico (UTMs universais)
 *
 * Também oferece `cleanUrl()` para remover parâmetros de rastreamento
 * de terceiros antes de armazenar no banco.
 */

import { Injectable } from '@nestjs/common';

// ---------------------------------------------------------------------------
// Padrões de detecção de loja
// ---------------------------------------------------------------------------

interface StorePattern {
  name: string;
  patterns: RegExp[];
}

const STORE_PATTERNS: StorePattern[] = [
  {
    name: 'amazon',
    patterns: [/amazon\.com\.br/, /amzn\.to/, /amzn\.com/],
  },
  {
    name: 'mercadolivre',
    patterns: [/mercadolivre\.com\.br/, /produto\.mercadolivre/, /mlb\d+/i],
  },
  {
    name: 'magazineluiza',
    patterns: [/magazineluiza\.com\.br/, /magalu\.com\.br/],
  },
  {
    name: 'americanas',
    patterns: [/americanas\.com\.br/],
  },
  {
    name: 'shopee',
    patterns: [/shopee\.com\.br/],
  },
  {
    name: 'casasbahia',
    patterns: [/casasbahia\.com\.br/],
  },
  {
    name: 'aliexpress',
    patterns: [/aliexpress\.com/, /s\.click\.aliexpress\.com/],
  },
];

// Parâmetros de rastreamento a remover na limpeza de URL
const TRACKING_PARAMS = [
  'fbclid', 'gclid', 'msclkid', 'ttclid',
  'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
  'ref', 'ref_', 'pf_rd_p', 'pf_rd_r', 'pf_rd_m', 'pf_rd_s', 'pf_rd_t', 'pf_rd_i',
  'pd_rd_i', 'pd_rd_r', 'pd_rd_w', 'pd_rd_wg', '_encoding',
  'qid', 'sprefix', 'sr', 'dib', 'dib_tag',
];

// ---------------------------------------------------------------------------
// Serviço
// ---------------------------------------------------------------------------

@Injectable()
export class AffiliateService {

  /**
   * Detecta o nome da loja a partir da URL.
   * @returns Nome da loja (ex: 'amazon') ou null
   */
  detectStore(url: string): string | null {
    for (const store of STORE_PATTERNS) {
      if (store.patterns.some((p) => p.test(url))) {
        return store.name;
      }
    }
    return null;
  }

  /**
   * Gera a URL de afiliado para o marketplace detectado.
   * @returns { affiliateUrl, store }
   */
  generateAffiliateUrl(url: string): { affiliateUrl: string; store: string } {
    const store = this.detectStore(url) ?? 'generic';

    try {
      switch (store) {
        case 'amazon':
          return { affiliateUrl: this.addAmazonAffiliate(url), store };
        case 'mercadolivre':
          return { affiliateUrl: this.addMercadoLivreAffiliate(url), store };
        default:
          return { affiliateUrl: this.addGenericUtm(url, store), store };
      }
    } catch {
      return { affiliateUrl: url, store };
    }
  }

  /**
   * Remove parâmetros de rastreamento da URL antes de persistir no banco.
   * Mantém apenas parâmetros relevantes para identificação do produto.
   */
  cleanUrl(url: string): string {
    try {
      const parsed = new URL(url);
      for (const param of TRACKING_PARAMS) {
        parsed.searchParams.delete(param);
      }
      return parsed.toString();
    } catch {
      return url;
    }
  }

  // -------------------------------------------------------------------------
  // Implementações por loja
  // -------------------------------------------------------------------------

  private addAmazonAffiliate(url: string): string {
    const parsed = new URL(url);
    const tag = process.env.AMAZON_AFFILIATE_TAG;
    if (tag) parsed.searchParams.set('tag', tag);
    return parsed.toString();
  }

  private addMercadoLivreAffiliate(url: string): string {
    const parsed = new URL(url);
    parsed.searchParams.set('utm_source', 'poupi');
    parsed.searchParams.set('utm_medium', 'affiliate');
    parsed.searchParams.set('utm_campaign', 'price_alert');
    const partnerId = process.env.ML_PARTNER_ID;
    if (partnerId) parsed.searchParams.set('partner_id', partnerId);
    return parsed.toString();
  }

  private addGenericUtm(url: string, store: string): string {
    const parsed = new URL(url);
    parsed.searchParams.set('utm_source', 'poupi');
    parsed.searchParams.set('utm_medium', 'affiliate');
    parsed.searchParams.set('utm_campaign', store);
    return parsed.toString();
  }
}
