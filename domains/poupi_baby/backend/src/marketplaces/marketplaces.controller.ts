import {
  Body,
  Controller,
  Delete,
  Get,
  Param,
  Patch,
  Post,
  UseGuards,
} from '@nestjs/common';

import { AuthGuard } from '@nestjs/passport';

import { CreateMarketplaceDto } from './dto/create-marketplace.dto';
import { UpdateMarketplaceDto } from './dto/update-marketplace.dto';

import { MarketplacesService } from './marketplaces.service';

@UseGuards(AuthGuard('jwt'))
@Controller('marketplaces')
export class MarketplacesController {
  constructor(
    private readonly marketplacesService: MarketplacesService,
  ) {}

  @Post()
  create(@Body() body: CreateMarketplaceDto) {
    return this.marketplacesService.create(body);
  }

  @Get()
  findAll() {
    return this.marketplacesService.findAll();
  }

  @Get(':id')
  findOne(@Param('id') id: string) {
    return this.marketplacesService.findOne(id);
  }

  @Patch(':id')
  update(
    @Param('id') id: string,
    @Body() body: UpdateMarketplaceDto,
  ) {
    return this.marketplacesService.update(id, body);
  }

  @Delete(':id')
  remove(@Param('id') id: string) {
    return this.marketplacesService.remove(id);
  }
}