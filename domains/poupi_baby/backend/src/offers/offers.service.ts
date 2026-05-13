import {
  Injectable,
  NotFoundException,
} from '@nestjs/common';

import { PrismaService } from '../prisma/prisma.service';
import { Prisma } from '@prisma/client';

import { CreateOfferDto } from './dto/create-offer.dto';
import { UpdateOfferDto } from './dto/update-offer.dto';

@Injectable()
export class OffersService {
  constructor(private prisma: PrismaService) {}

  async create(data: CreateOfferDto) {
    return this.prisma.offer.create({
      data,
      include: {
        product: true,
        marketplace: true,
      },
    });
  }

  async findAll() {
    return this.prisma.offer.findMany({
      where: { deletedAt: null },
      include: {
        product: true,
        marketplace: true,
      },
      orderBy: { updatedAt: 'desc' },
    });
  }

  async findOne(id: string) {
    // BUG-16: retorna 404 quando não encontrado
    const offer = await this.prisma.offer.findUnique({
      where: { id, deletedAt: null },
      include: {
        product: true,
        marketplace: true,
      },
    });

    if (!offer) {
      throw new NotFoundException(`Oferta não encontrada: ${id}`);
    }

    return offer;
  }

  async update(id: string, data: UpdateOfferDto) {
    // BUG-19: captura P2025 e retorna 404 em vez de 500
    try {
      return await this.prisma.offer.update({
        where: { id, deletedAt: null },
        data,
      });
    } catch (e) {
      if (
        e instanceof Prisma.PrismaClientKnownRequestError &&
        e.code === 'P2025'
      ) {
        throw new NotFoundException(`Oferta não encontrada: ${id}`);
      }
      throw e;
    }
  }

  async remove(id: string) {
    // BUG-19: captura P2025 e retorna 404 em vez de 500
    try {
      return await this.prisma.offer.update({
        where: { id, deletedAt: null },
        data: { deletedAt: new Date() },
      });
    } catch (e) {
      if (
        e instanceof Prisma.PrismaClientKnownRequestError &&
        e.code === 'P2025'
      ) {
        throw new NotFoundException(`Oferta não encontrada: ${id}`);
      }
      throw e;
    }
  }
}
