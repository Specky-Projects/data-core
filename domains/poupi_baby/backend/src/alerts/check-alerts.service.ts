import { Injectable, Logger } from '@nestjs/common';

import { Cron } from '@nestjs/schedule';

import { PrismaService } from '../prisma/prisma.service';

import { NotificationsService }
from '../notifications/notifications.service';

const BATCH_SIZE = 100;
const ALERT_COOLDOWN_HOURS = 24;

@Injectable()
export class CheckAlertsService {

  private readonly logger = new Logger(CheckAlertsService.name);

  constructor(
    private prisma: PrismaService,

    private notificationsService: NotificationsService,
  ) {}

  // Executa a cada 6 horas (offset +2h do crawler para evitar colisao)
  @Cron('0 0 2-23/6 * * *')
  async checkAlerts() {

    this.logger.log('Verificando alertas...');

    let skip = 0;

    // BUG-22: processar em lotes para não carregar tudo em memória
    while (true) {
      const alerts = await this.prisma.alert.findMany({
        where: { active: true },
        include: {
          product: {
            include: {
              // BUG-23: filtrar ofertas deletadas e indisponíveis
              offers: {
                where: {
                  deletedAt: null,
                  availability: true,
                },
              },
            },
          },
          user: true,
        },
        take: BATCH_SIZE,
        skip,
      });

      if (alerts.length === 0) break;

      for (const alert of alerts) {

        const offers = alert.product.offers;

        if (!offers.length) continue;

        const lowestOffer = offers.reduce((lowest, current) =>
          Number(current.price) < Number(lowest.price) ? current : lowest,
        );

        const lowestPrice = Number(lowestOffer.price);
        const targetPrice = Number(alert.targetPrice);

        if (lowestPrice <= targetPrice) {

          // BUG-10: desativar o alerta após disparar para evitar spam
          await this.prisma.alert.update({
            where: { id: alert.id },
            data: { active: false },
          });

          this.logger.log(
            `Alerta disparado — Usuário: ${alert.user.email} | Produto: ${alert.product.title} | Alvo: ${targetPrice} | Atual: ${lowestPrice}`,
          );

          await this.notificationsService.sendPriceAlert({
            email: alert.user.email,
            userName: alert.user.name ?? alert.user.email.split('@')[0],
            productTitle: alert.product.title,
            productUrl: lowestOffer.productUrl,
            productImageUrl: alert.product.imageUrl,
            currentPrice: lowestPrice,
            previousPrice: lowestPrice,   // safety-net: sem histórico de variação aqui
            targetPrice: Number(alert.targetPrice),
            marketplace: '',
          });
        }
      }

      if (alerts.length < BATCH_SIZE) break;

      skip += BATCH_SIZE;
    }
  }
}
