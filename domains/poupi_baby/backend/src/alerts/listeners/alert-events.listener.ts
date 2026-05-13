import { Injectable, Logger } from '@nestjs/common';
import { OnEvent } from '@nestjs/event-emitter';
import { PrismaService } from '../../prisma/prisma.service';
import { EventBusService } from '../../shared/events/event-bus.service';
import { DOMAIN_EVENTS, SmartAlertType } from '../../shared/events/domain-events';
import type { OfferPriceUpdatedPayload } from '../../shared/events/domain-events';
import { NotificationQueueService } from '../../notifications/queue/notification-queue.service';

const PRICE_DROP_PERCENT = 5;
const ALERT_COOLDOWN_HOURS = 24;

type Watcher = {
  userId: string;
  email: string;
  name: string | null;
  targetPrice?: number | null;
};

@Injectable()
export class AlertEventsListener {
  private readonly logger = new Logger(AlertEventsListener.name);

  constructor(
    private readonly prisma: PrismaService,
    private readonly eventBus: EventBusService,
    private readonly notificationQueue: NotificationQueueService,
  ) {}

  @OnEvent(DOMAIN_EVENTS.OFFER_PRICE_UPDATED)
  async handlePriceUpdated(event: { payload: OfferPriceUpdatedPayload }): Promise<void> {
    const { offerId, productId, marketplace, newPrice, oldPrice } = event.payload;
    if (oldPrice !== null && newPrice >= oldPrice) return;

    try {
      const product = await this.productForAlert(productId, offerId);
      if (!product) return;

      const isNewLowest = await this.isHistoricalLowest(productId, newPrice);
      const dropPct = oldPrice ? ((oldPrice - newPrice) / oldPrice) * 100 : 0;

      if (isNewLowest) {
        await this.dispatchSmartAlert({
          type: 'NEW_LOWEST_PRICE',
          offerId,
          productId,
          marketplace,
          currentPrice: newPrice,
          previousPrice: oldPrice,
          reason: 'Preco atual igualou ou superou a menor minima historica registrada.',
          product,
        });
      } else if (dropPct >= PRICE_DROP_PERCENT) {
        await this.dispatchSmartAlert({
          type: 'PRICE_DROP',
          offerId,
          productId,
          marketplace,
          currentPrice: newPrice,
          previousPrice: oldPrice,
          reason: `Queda de ${Math.round(dropPct)}% em relacao ao preco anterior.`,
          product,
        });
      }
    } catch (err: any) {
      this.logger.error(`[smart-alerts] Erro ao processar queda de preco: ${err.message}`);
    }
  }

  @OnEvent(DOMAIN_EVENTS.OFFER_BACK_IN_STOCK)
  async handleRestocked(event: { payload: OfferPriceUpdatedPayload }): Promise<void> {
    const { offerId, productId, marketplace, newPrice, oldPrice } = event.payload;

    try {
      const product = await this.productForAlert(productId, offerId);
      if (!product) return;

      await this.dispatchSmartAlert({
        type: 'RESTOCKED',
        offerId,
        productId,
        marketplace,
        currentPrice: newPrice,
        previousPrice: oldPrice,
        reason: 'Oferta monitorada voltou a ficar disponivel.',
        product,
      });
    } catch (err: any) {
      this.logger.error(`[smart-alerts] Erro ao processar restock: ${err.message}`);
    }
  }

  private async isHistoricalLowest(productId: string, currentPrice: number): Promise<boolean> {
    const aggregate = await this.prisma.priceHistory.aggregate({
      where: {
        offer: {
          productId,
          deletedAt: null,
        },
      },
      _min: { price: true },
    });

    const historicalMin = aggregate._min.price;
    if (historicalMin === null) return false;
    return currentPrice <= Number(historicalMin);
  }

  private async dispatchSmartAlert(params: {
    type: SmartAlertType;
    offerId: string;
    productId: string;
    marketplace: string;
    currentPrice: number;
    previousPrice: number | null;
    reason: string;
    product: {
      title: string;
      imageUrl: string | null;
      productUrl: string;
    };
  }): Promise<void> {
    const watchers = await this.watchersForProduct(params.productId);
    if (watchers.length === 0) return;

    let sent = 0;
    for (const watcher of watchers) {
      if (await this.isCoolingDown(watcher.userId, params.productId, params.type)) continue;

      await this.notificationQueue.sendSmartAlert({
        userId: watcher.userId,
        email: watcher.email,
        userName: watcher.name ?? watcher.email.split('@')[0],
        productTitle: params.product.title,
        productUrl: params.product.productUrl,
        productImageUrl: params.product.imageUrl,
        currentPrice: params.currentPrice,
        previousPrice: params.previousPrice,
        marketplace: params.marketplace,
        type: params.type,
        reason: params.reason,
      });

      await this.markSent(watcher.userId, params.productId, params.type, {
        offerId: params.offerId,
        marketplace: params.marketplace,
        currentPrice: params.currentPrice,
        previousPrice: params.previousPrice,
      });

      this.eventBus.emit(this.domainEventFor(params.type), {
        userId: watcher.userId,
        productId: params.productId,
        offerId: params.offerId,
        marketplace: params.marketplace,
        type: params.type,
        currentPrice: params.currentPrice,
        previousPrice: params.previousPrice,
        productTitle: params.product.title,
        productUrl: params.product.productUrl,
        productImageUrl: params.product.imageUrl,
        reason: params.reason,
      });

      sent++;
    }

    if (sent > 0) {
      this.logger.log(`[smart-alerts] ${params.type}: ${sent} usuario(s) notificado(s) productId=${params.productId}`);
    }
  }

  private async productForAlert(productId: string, offerId: string) {
    const [product, offer] = await Promise.all([
      this.prisma.product.findUnique({
        where: { id: productId },
        select: { title: true, imageUrl: true },
      }),
      this.prisma.offer.findUnique({
        where: { id: offerId },
        select: { productUrl: true },
      }),
    ]);

    if (!product || !offer) return null;
    return { ...product, productUrl: offer.productUrl };
  }

  private async watchersForProduct(productId: string): Promise<Watcher[]> {
    const fromAlerts = await this.prisma.alert.findMany({
      where: { productId, active: true },
      include: { user: { select: { id: true, email: true, name: true } } },
    });

    const watchers = new Map<string, Watcher>();
    for (const alert of fromAlerts) {
      watchers.set(alert.userId, {
        userId: alert.userId,
        email: alert.user.email,
        name: alert.user.name,
        targetPrice: Number(alert.targetPrice),
      });
    }

    for (const watcher of await this.watchlistUsers(productId)) {
      watchers.set(watcher.userId, watcher);
    }

    return [...watchers.values()];
  }

  private async watchlistUsers(productId: string): Promise<Watcher[]> {
    try {
      return await this.prisma.$queryRaw<Watcher[]>`
        SELECT u.id as "userId", u.email, u.name
        FROM watchlists w
        INNER JOIN users u ON u.id = w.user_id
        WHERE w.product_id = ${productId}::uuid
          AND w.active = true
          AND w.deleted_at IS NULL
          AND u.deleted_at IS NULL
      `;
    } catch {
      return [];
    }
  }

  private async isCoolingDown(
    userId: string,
    productId: string,
    type: SmartAlertType,
  ): Promise<boolean> {
    const since = new Date(Date.now() - ALERT_COOLDOWN_HOURS * 3600_000);
    const recent = await this.prisma.userEvent.findMany({
      where: {
        userId,
        eventType: `smart_alert.${type}`,
        occurredAt: { gte: since },
      },
      select: { payload: true },
      orderBy: { occurredAt: 'desc' },
      take: 20,
    });

    return recent.some((event) => this.parsePayload(event.payload).productId === productId);
  }

  private async markSent(
    userId: string,
    productId: string,
    type: SmartAlertType,
    payload: Record<string, unknown>,
  ): Promise<void> {
    await this.prisma.userEvent.create({
      data: {
        userId,
        eventType: `smart_alert.${type}`,
        payload: JSON.stringify({ productId, ...payload }),
      },
    });
  }

  private parsePayload(payload: string): { productId?: string } {
    try {
      return JSON.parse(payload);
    } catch {
      return {};
    }
  }

  private domainEventFor(type: SmartAlertType) {
    if (type === 'NEW_LOWEST_PRICE') return DOMAIN_EVENTS.ALERT_NEW_LOWEST_PRICE;
    if (type === 'PRICE_DROP') return DOMAIN_EVENTS.ALERT_PRICE_DROP;
    return DOMAIN_EVENTS.ALERT_RESTOCKED;
  }
}
