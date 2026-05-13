import axios, { AxiosRequestConfig } from 'axios';
import * as cheerio from 'cheerio';
import {
  detectBlock,
  getRandomHeaders,
  makeProduct,
  parsePrice,
  randomSleep,
} from '../../scrapers/base.scraper';
import {
  extractFromProductJsonLd,
  findProductJsonLd,
} from '../../scrapers/strategy';
import {
  ScrapeContext,
  SourceAdapter,
  SourceScrapeResult,
} from '../source-adapter.interface';
import { BrowserSessionService } from '../browser-session.service';
import { classifyScrapeError } from '../scrape-error';

const PRICE_SELECTORS = [
  '[class*="sellingPriceValue"]',
  '[class*="sellingPrice"]',
  '[class*="currencyContainer"]',
  'span[class*="Price"] span[class*="currencyContainer"]',
  "[itemprop='price']",
];

const ORIGINAL_PRICE_SELECTORS = [
  '[class*="listPriceValue"]',
  '[class*="listPrice"]',
  'del [class*="currencyContainer"]',
  's [class*="Price"]',
];

const TITLE_SELECTORS = [
  '[class*="productName"] h1',
  '[class*="ProductName"] h1',
  'h1[class*="Title"]',
  'h1',
  "[itemprop='name']",
];

const IMAGE_SELECTORS = [
  '[class*="productImageTag"]',
  '[class*="productImage"] img',
  'figure img[class*="product"]',
  "[itemprop='image']",
];

const UNAVAILABLE = [
  'produto indisponivel',
  'esgotado',
  'sem estoque',
  'fora de estoque',
  'indisponivel',
];

export abstract class VtexPharmacyAdapter implements SourceAdapter {
  readonly concurrency = 1;

  protected constructor(
    readonly source: string,
    private readonly hosts: string[],
    private readonly browserSession?: BrowserSessionService,
  ) {}

  supports(url: string, marketplace?: string): boolean {
    if (marketplace === this.source) return true;
    let hostname: string;
    try {
      hostname = new URL(url).hostname.replace(/^www\./, '');
    } catch {
      return false;
    }
    return this.hosts.some((host) => hostname === host || hostname.endsWith(`.${host}`));
  }

  async scrape(context: ScrapeContext): Promise<SourceScrapeResult> {
    const response = await this.fetchHtml(context);
    return this.parseHtml(response, context);
  }

  protected parseHtml(response: {
    html: string | null;
    finalUrl?: string;
    statusCode?: number;
    responseHeaders?: Record<string, string | string[] | undefined>;
    screenshotPath?: string | null;
  }, context: ScrapeContext): SourceScrapeResult {
    const html = response.html;

    if (!html || detectBlock(html)) {
      return {
        ...makeProduct({
          success: false,
          store: this.source,
          error: 'CAPTCHA, bloqueio ou HTML vazio detectado',
        }),
        errorType: classifyScrapeError({
          statusCode: response.statusCode,
          error: 'CAPTCHA, bloqueio ou HTML vazio detectado',
          html,
        }),
        htmlSnapshot: html,
        finalUrl: response.finalUrl,
        statusCode: response.statusCode,
        responseHeaders: response.responseHeaders,
        proxy: context.proxy,
        screenshotPath: response.screenshotPath,
      };
    }

    const fromJsonLd = this.extractJsonLd(html);
    if (fromJsonLd?.price) {
      return {
        ...makeProduct({ success: true, store: this.source, ...fromJsonLd }),
        finalUrl: response.finalUrl,
        statusCode: response.statusCode,
      };
    }

    const $ = cheerio.load(html);
    const price = this.extractPrice($);
    if (!price) {
      return {
        ...makeProduct({
          success: false,
          store: this.source,
          error: 'Preco nao encontrado',
        }),
        errorType: classifyScrapeError({
          statusCode: response.statusCode,
          error: 'Preco nao encontrado',
          html,
        }),
        htmlSnapshot: html,
        finalUrl: response.finalUrl,
        statusCode: response.statusCode,
        responseHeaders: response.responseHeaders,
        proxy: context.proxy,
        screenshotPath: response.screenshotPath,
      };
    }

    return {
      ...makeProduct({
        success: true,
        store: this.source,
        price,
        name: this.extractTitle($),
        imageUrl: this.extractImage($),
        originalPrice: this.extractOriginalPrice($),
        availability: this.checkAvailability($),
      }),
      finalUrl: response.finalUrl,
      statusCode: response.statusCode,
    };
  }

  private async fetchHtml(context: ScrapeContext): Promise<{
    html: string | null;
    finalUrl?: string;
    statusCode?: number;
    responseHeaders?: Record<string, string | string[] | undefined>;
    screenshotPath?: string | null;
  }> {
    try {
      await randomSleep(
        context.adaptiveDelay?.minMs ?? 3_000,
        context.adaptiveDelay?.maxMs ?? 12_000,
      );

      const browserResult = await this.browserSession?.fetchHtml(
        context.url,
        this.source,
        context.proxy,
      );
      if (browserResult) return browserResult;

      const config: AxiosRequestConfig = {
        headers: getRandomHeaders(this.source),
        timeout: 12_000,
        maxRedirects: 5,
        responseType: 'text',
        decompress: true,
        validateStatus: (status) => status >= 200 && status < 500,
      };

      const proxy = this.proxyConfig(context.proxy?.url);
      if (proxy) config.proxy = proxy;

      const response = await axios.get<string>(context.url, config);
      return {
        html: response.data,
        finalUrl: response.request?.res?.responseUrl ?? context.url,
        statusCode: response.status,
        responseHeaders: response.headers as Record<string, string | string[] | undefined>,
      };
    } catch (err) {
      return {
        html: null,
        finalUrl: context.url,
        statusCode: (err as any)?.response?.status,
        responseHeaders: (err as any)?.response?.headers,
      };
    }
  }

  private extractJsonLd(html: string) {
    const block = findProductJsonLd(html);
    if (!block) return null;

    const extracted = extractFromProductJsonLd(block);
    if (!extracted.price) return null;

    const $ = cheerio.load(html);
    return {
      ...extracted,
      imageUrl: extracted.imageUrl ?? this.extractImage($),
      availability: extracted.availability && this.checkAvailability($),
    };
  }

  private extractPrice($: cheerio.CheerioAPI): number | null {
    for (const selector of PRICE_SELECTORS) {
      const value =
        $(selector).first().attr('content') ??
        $(selector).first().text().trim();
      const price = parsePrice(value);
      if (price) return price;
    }

    const match = $.html().match(/R\$\s*([\d.]+,\d{2})/);
    return match ? parsePrice(match[1]) : null;
  }

  private extractOriginalPrice($: cheerio.CheerioAPI): number | null {
    for (const selector of ORIGINAL_PRICE_SELECTORS) {
      const price = parsePrice($(selector).first().text().trim());
      if (price) return price;
    }
    return null;
  }

  private extractTitle($: cheerio.CheerioAPI): string | null {
    for (const selector of TITLE_SELECTORS) {
      const text = $(selector).first().text().trim().replace(/\s+/g, ' ');
      if (text && text.length > 3) return text;
    }
    return null;
  }

  private extractImage($: cheerio.CheerioAPI): string | null {
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

  private checkAvailability($: cheerio.CheerioAPI): boolean {
    const body = $('body')
      .text()
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .toLowerCase();
    return !UNAVAILABLE.some((keyword) => body.includes(keyword));
  }

  private proxyConfig(proxyUrl?: string): AxiosRequestConfig['proxy'] {
    if (!proxyUrl) return undefined;
    try {
      const url = new URL(proxyUrl);
      return {
        protocol: url.protocol.replace(':', ''),
        host: url.hostname,
        port: Number(url.port || 80),
        auth: url.username
          ? { username: url.username, password: url.password }
          : undefined,
      };
    } catch {
      return undefined;
    }
  }
}
