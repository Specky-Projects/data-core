import {
  Injectable,
  NotFoundException,
} from '@nestjs/common';

import { PrismaService } from '../prisma/prisma.service';
import { Prisma } from '@prisma/client';

import { CreateMarketplaceDto } from './dto/create-marketplace.dto';
import { UpdateMarketplaceDto } from './dto/update-marketplace.dto';

@Injectable()
export class MarketplacesService {
  constructor(private prisma: PrismaService) {}

  async create(data: CreateMarketplaceDto) {
    return this.prisma.marketplace.create({ data });
  }

  async findAll() {
    return this.prisma.marketplace.findMany({
      where: { active: true },
      orderBy: { name: 'asc' },
    });
  }

  async findOne(id: string) {
    // BUG-16: retorna 404 quando não encontrado
    const marketplace = await this.prisma.marketplace.findUnique({
      where: { id },
    });

    if (!marketplace) {
      throw new NotFoundException(`Marketplace não encontrado: ${id}`);
    }

    return marketplace;
  }

  async update(id: string, data: UpdateMarketplaceDto) {
    // BUG-19: captura P2025 e retorna 404 em vez de 500
    try {
      return await this.prisma.marketplace.update({
        where: { id },
        data,
      });
    } catch (e) {
      if (
        e instanceof Prisma.PrismaClientKnownRequestError &&
        e.code === 'P2025'
      ) {
        throw new NotFoundException(`Marketplace não encontrado: ${id}`);
      }
      throw e;
    }
  }

  async remove(id: string) {
    // BUG-18: soft delete via active=false para preservar histórico de preços
    try {
      return await this.prisma.marketplace.update({
        where: { id },
        data: { active: false },
      });
    } catch (e) {
      if (
        e instanceof Prisma.PrismaClientKnownRequestError &&
        e.code === 'P2025'
      ) {
        throw new NotFoundException(`Marketplace não encontrado: ${id}`);
      }
      throw e;
    }
  }
}
