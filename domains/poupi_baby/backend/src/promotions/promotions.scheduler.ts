import { Injectable, Logger } from '@nestjs/common';
import { Cron } from '@nestjs/schedule';
import { PromotionsService } from './promotions.service';

@Injectable()
export class PromotionsScheduler {
  private readonly logger = new Logger(PromotionsScheduler.name);

  constructor(private readonly promotions: PromotionsService) {}

  @Cron('0 0 */2 * * *')
  async publishTelegramRadar() {
    if (process.env.TELEGRAM_RADAR_ENABLED !== 'true') return;

    const result = await this.promotions.publishRadar({
      dryRun: false,
      limit: Number(process.env.TELEGRAM_RADAR_LIMIT ?? 3),
    });

    this.logger.log(
      `Radar Telegram: ${result.sent} enviados, ${result.eligible} elegiveis, ${result.analyzed} analisados.`,
    );
  }
}
