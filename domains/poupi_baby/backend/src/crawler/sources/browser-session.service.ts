import { Injectable, Logger, OnModuleDestroy } from '@nestjs/common';
import { existsSync } from 'fs';
import { mkdir, writeFile } from 'fs/promises';
import { join } from 'path';
import { createHash } from 'crypto';
import { detectBlock, getRandomHeaders, randomSleep } from '../scrapers/base.scraper';

type ProxyConfig = {
  url?: string;
};

type BrowserFetchResult = {
  html: string;
  finalUrl: string;
  statusCode?: number;
  responseHeaders?: Record<string, string>;
  screenshotPath?: string | null;
};

@Injectable()
export class BrowserSessionService implements OnModuleDestroy {
  private readonly logger = new Logger(BrowserSessionService.name);
  private browser: any = null;
  private playwright: any = null;
  private readonly contexts = new Map<string, any>();
  private readonly enabled = process.env.SCRAPER_BROWSER_MODE === 'true';

  get isEnabled(): boolean {
    return this.enabled;
  }

  async fetchHtml(
    url: string,
    source: string,
    proxy?: ProxyConfig,
  ): Promise<BrowserFetchResult | null> {
    if (!this.enabled) return null;

    try {
      const context = await this.getContext(source, proxy);
      const page = await context.newPage();
      try {
        await this.performLightBehavior(page);
        const response = await page.goto(url, {
          waitUntil: 'domcontentloaded',
          timeout: 30_000,
        });
        await this.performLightBehavior(page);

        const html = await page.content();
        const statusCode = response?.status();
        const screenshotPath = (typeof statusCode === 'number' && statusCode >= 400) || detectBlock(html)
          ? await this.saveFailureScreenshot(page, source, proxy)
          : null;

        return {
          html,
          finalUrl: page.url(),
          statusCode,
          responseHeaders: response ? await response.allHeaders().catch(() => undefined) : undefined,
          screenshotPath,
        };
      } finally {
        await this.persistStorageState(source, proxy, context);
        await page.close().catch(() => undefined);
      }
    } catch (err) {
      this.logger.warn(`[browser] fallback para HTTP em ${source}: ${(err as Error).message}`);
      return null;
    }
  }

  async onModuleDestroy() {
    for (const context of this.contexts.values()) {
      await context.close().catch(() => undefined);
    }
    await this.browser?.close?.().catch(() => undefined);
  }

  private async getContext(source: string, proxy?: ProxyConfig) {
    const key = `${source}:${proxy?.url ?? 'direct'}`;
    const existing = this.contexts.get(key);
    if (existing) return existing;

    const browser = await this.getBrowser();
    const headers = getRandomHeaders(source);
    const storageState = this.storagePath(source, proxy);
    const context = await browser.newContext({
      userAgent: headers['User-Agent'],
      locale: 'pt-BR',
      timezoneId: 'America/Sao_Paulo',
      viewport: { width: 1366, height: 768 },
      extraHTTPHeaders: this.toPlaywrightHeaders(headers),
      proxy: proxy?.url ? { server: proxy.url } : undefined,
      storageState: existsSync(storageState) ? storageState : undefined,
    });

    await context.addInitScript(() => {
      Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
      Object.defineProperty(navigator, 'languages', { get: () => ['pt-BR', 'pt'] });
      Object.defineProperty(navigator, 'plugins', {
        get: () => [
          { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer' },
          { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai' },
          { name: 'Native Client', filename: 'internal-nacl-plugin' },
        ],
      });
      Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
      Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 });
      Object.defineProperty(navigator, 'maxTouchPoints', { get: () => 0 });

      const originalQuery = window.navigator.permissions?.query;
      if (originalQuery) {
        window.navigator.permissions.query = (parameters: any) =>
          parameters.name === 'notifications'
            ? Promise.resolve({ state: (globalThis as any).Notification?.permission ?? 'default' })
            : originalQuery.call(window.navigator.permissions, parameters);
      }

      Object.defineProperty(window, 'chrome', {
        get: () => ({
          app: { isInstalled: false },
          runtime: {},
          csi: () => undefined,
          loadTimes: () => undefined,
        }),
      });

      Object.defineProperty(window, 'outerWidth', { get: () => window.innerWidth + 16 });
      Object.defineProperty(window, 'outerHeight', { get: () => window.innerHeight + 88 });

      const getParameter = WebGLRenderingContext.prototype.getParameter;
      WebGLRenderingContext.prototype.getParameter = function patchedGetParameter(parameter) {
        if (parameter === 37445) return 'Intel Inc.';
        if (parameter === 37446) return 'Intel Iris OpenGL Engine';
        return getParameter.call(this, parameter);
      };
    });

    await context.route('**/*', (route: any) => {
      const type = route.request().resourceType();
      if (['image', 'font', 'media'].includes(type)) return route.abort();
      return route.continue();
    });

    this.contexts.set(key, context);
    return context;
  }

  private async getBrowser() {
    if (this.browser) return this.browser;

    const dynamicImport = Function('specifier', 'return import(specifier)') as (
      specifier: string,
    ) => Promise<any>;
    this.playwright = await dynamicImport('playwright');
    this.browser = await this.playwright.chromium.launch({
      headless: true,
      args: [
        '--disable-blink-features=AutomationControlled',
        '--disable-dev-shm-usage',
        '--no-sandbox',
      ],
    });
    return this.browser;
  }

  private toPlaywrightHeaders(headers: Record<string, string>) {
    const copy = { ...headers };
    delete copy['User-Agent'];
    delete copy['Accept-Encoding'];
    return copy;
  }

  private storageDir(): string {
    return process.env.SCRAPER_SESSION_DIR ?? join(process.cwd(), '.scraper-sessions');
  }

  private storagePath(source: string, proxy?: ProxyConfig): string {
    const proxyKey = proxy?.url
      ? Buffer.from(proxy.url).toString('base64url').slice(0, 32)
      : 'direct';
    return join(this.storageDir(), `${source}-${proxyKey}.json`);
  }

  private async persistStorageState(source: string, proxy: ProxyConfig | undefined, context: any) {
    try {
      await mkdir(this.storageDir(), { recursive: true });
      const state = await context.storageState();
      await writeFile(this.storagePath(source, proxy), JSON.stringify(state), 'utf8');
    } catch (err) {
      this.logger.debug(`[browser] nao foi possivel persistir sessao: ${(err as Error).message}`);
    }
  }

  private screenshotDir(): string {
    return join(process.env.SCRAPER_SNAPSHOT_DIR ?? join(process.cwd(), 'storage', 'scraper-failures'), 'screenshots');
  }

  private async saveFailureScreenshot(page: any, source: string, proxy?: ProxyConfig): Promise<string | null> {
    try {
      await mkdir(this.screenshotDir(), { recursive: true });
      const hash = createHash('sha1')
        .update(`${source}:${proxy?.url ?? 'direct'}:${page.url()}:${Date.now()}`)
        .digest('hex')
        .slice(0, 12);
      const filename = `${new Date().toISOString().replace(/[:.]/g, '-')}-${source}-${hash}.png`;
      const filepath = join(this.screenshotDir(), filename);
      await page.screenshot({ path: filepath, fullPage: true });
      return filepath;
    } catch (err) {
      this.logger.debug(`[browser] nao foi possivel salvar screenshot: ${(err as Error).message}`);
      return null;
    }
  }

  private async performLightBehavior(page: any) {
    await randomSleep(700, 2_200);
    const x = 120 + Math.round(Math.random() * 600);
    const y = 120 + Math.round(Math.random() * 350);
    await page.mouse.move(x, y, { steps: 6 + Math.round(Math.random() * 8) }).catch(() => undefined);
    await page.evaluate(() => window.scrollBy(0, Math.round(80 + Math.random() * 240))).catch(() => undefined);
  }
}
