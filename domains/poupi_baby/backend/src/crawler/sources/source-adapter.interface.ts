import { ScrapedProduct } from '../scrapers/base.scraper';
import { ScrapeErrorType } from './scrape-error';

export interface ProxyConfig {
  url: string;
  label?: string;
}

export interface ScrapeContext {
  offerId?: string;
  externalId?: string;
  marketplace: string;
  url: string;
  attempt: number;
  priority: 'manual' | 'alert' | 'scheduler';
  proxy?: ProxyConfig;
  adaptiveDelay?: {
    minMs: number;
    maxMs: number;
  };
}

export interface SourceScrapeResult extends ScrapedProduct {
  htmlSnapshot?: string | null;
  finalUrl?: string;
  statusCode?: number;
  errorType?: ScrapeErrorType;
  responseHeaders?: Record<string, string | string[] | undefined>;
  proxy?: ProxyConfig;
  screenshotPath?: string | null;
}

export interface SourceAdapter {
  readonly source: string;
  readonly concurrency: number;
  supports(url: string, marketplace?: string): boolean;
  scrape(context: ScrapeContext): Promise<SourceScrapeResult>;
}
