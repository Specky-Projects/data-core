import { Injectable, NotFoundException, ForbiddenException } from '@nestjs/common';
import { randomUUID } from 'node:crypto';

import { PrismaService }
from '../prisma/prisma.service';

import { CreateAlertDto }
from './dto/create-alert.dto';

@Injectable()
export class AlertsService {

  constructor(
    private prisma: PrismaService,
  ) {}

  create(
    data: CreateAlertDto,

    userId: string,
  ) {

    return this.prisma.alert.create({
      data: {
        targetPrice: data.targetPrice,

        user: {
          connect: {
            id: userId,
          },
        },

        product: {
          connect: {
            id: data.productId,
          },
        },
      },
    });
  }

  myAlerts(userId: string) {
    return this.prisma.alert.findMany({
      where: { userId },
      include: { product: true },
      orderBy: { createdAt: 'desc' },
    });
  }

  async cancel(alertId: string, userId: string) {
    const alert = await this.prisma.alert.findUnique({
      where: { id: alertId },
    });

    if (!alert) throw new NotFoundException('Alerta não encontrado');
    if (alert.userId !== userId) throw new ForbiddenException('Sem permissão');

    return this.prisma.alert.update({
      where: { id: alertId },
      data: { active: false },
    });
  }

  async watch(productId: string, userId: string) {
    const product = await this.prisma.product.findUnique({
      where: { id: productId, deletedAt: null },
      select: { id: true },
    });
    if (!product) throw new NotFoundException('Produto nao encontrado');

    const id = randomUUID();
    await this.prisma.$executeRaw`
      INSERT INTO watchlists (id, user_id, product_id, active, created_at, deleted_at)
      VALUES (${id}::uuid, ${userId}::uuid, ${productId}::uuid, true, now(), null)
      ON CONFLICT (user_id, product_id)
      DO UPDATE SET active = true, deleted_at = null
    `;

    return { productId, active: true };
  }

  async myWatchlist(userId: string) {
    return this.prisma.$queryRaw`
      SELECT
        w.id,
        w.product_id as "productId",
        w.created_at as "createdAt",
        p.title,
        p.image_url as "imageUrl"
      FROM watchlists w
      INNER JOIN products p ON p.id = w.product_id
      WHERE w.user_id = ${userId}::uuid
        AND w.active = true
        AND w.deleted_at IS NULL
        AND p.deleted_at IS NULL
      ORDER BY w.created_at DESC
    `;
  }

  async unwatch(productId: string, userId: string) {
    const updated = await this.prisma.$executeRaw`
      UPDATE watchlists
      SET active = false, deleted_at = now()
      WHERE user_id = ${userId}::uuid
        AND product_id = ${productId}::uuid
        AND active = true
    `;
    if (updated === 0) throw new NotFoundException('Produto nao encontrado na watchlist');
    return { productId, active: false };
  }
}
