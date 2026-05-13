import { Injectable, Logger } from '@nestjs/common';
import * as crypto from 'node:crypto';
import * as fs from 'node:fs/promises';
import * as path from 'node:path';

@Injectable()
export class HtmlSnapshotService {
  private readonly logger = new Logger(HtmlSnapshotService.name);
  private readonly baseDir =
    process.env.SCRAPER_SNAPSHOT_DIR ??
    path.join(process.cwd(), 'storage', 'scraper-failures');

  async saveFailure(params: {
    marketplace: string;
    offerId?: string;
    url: string;
    html?: string | null;
    error?: string | null;
    errorType?: string | null;
    statusCode?: number;
    finalUrl?: string;
    proxyLabel?: string;
    proxyUrl?: string;
    responseHeaders?: Record<string, string | string[] | undefined>;
    screenshotPath?: string | null;
  }): Promise<string | null> {
    if (!params.html && !params.screenshotPath) return null;

    try {
      await fs.mkdir(this.baseDir, { recursive: true });
      const hash = crypto
        .createHash('sha1')
        .update(`${params.marketplace}:${params.offerId ?? ''}:${params.url}:${Date.now()}`)
        .digest('hex')
        .slice(0, 12);
      const safeMarketplace = params.marketplace.replace(/[^a-z0-9_-]/gi, '-').toLowerCase();
      const filename = `${new Date().toISOString().replace(/[:.]/g, '-')}-${safeMarketplace}-${hash}.html`;
      const filepath = path.join(this.baseDir, filename);
      const metadataPath = filepath.replace(/\.html$/, '.json');

      const header = [
        '<!--',
        `marketplace: ${params.marketplace}`,
        `offerId: ${params.offerId ?? ''}`,
        `url: ${params.url}`,
        `finalUrl: ${params.finalUrl ?? ''}`,
        `statusCode: ${params.statusCode ?? ''}`,
        `errorType: ${params.errorType ?? ''}`,
        `error: ${params.error ?? ''}`,
        `proxyLabel: ${params.proxyLabel ?? ''}`,
        `screenshotPath: ${params.screenshotPath ?? ''}`,
        '-->',
        '',
      ].join('\n');

      if (params.html) await fs.writeFile(filepath, `${header}${params.html}`, 'utf8');
      await fs.writeFile(metadataPath, JSON.stringify({
        marketplace: params.marketplace,
        offerId: params.offerId,
        url: params.url,
        finalUrl: params.finalUrl,
        statusCode: params.statusCode,
        errorType: params.errorType,
        error: params.error,
        proxyLabel: params.proxyLabel,
        proxyUrl: params.proxyUrl,
        responseHeaders: params.responseHeaders,
        screenshotPath: params.screenshotPath,
        capturedAt: new Date().toISOString(),
      }, null, 2), 'utf8');
      return filepath;
    } catch (err) {
      this.logger.warn(`Falha ao salvar snapshot HTML: ${(err as Error).message}`);
      return null;
    }
  }
}
