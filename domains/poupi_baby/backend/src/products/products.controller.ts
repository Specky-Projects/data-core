import {
  Body,
  Controller,
  Delete,
  Get,
  Param,
  Patch,
  Post,
  Req,
  UseGuards,
} from '@nestjs/common';
import { AuthGuard } from '@nestjs/passport';
import { Request } from 'express';
import { ProductsService } from './products.service';
import { CreateProductDto } from './dto/create-product.dto';
import { UpdateProductDto } from './dto/update-product.dto';

interface AuthReq extends Request {
  user: { userId: string; email: string };
}

@UseGuards(AuthGuard('jwt'))
@Controller('products')
export class ProductsController {
  constructor(private readonly productsService: ProductsService) {}

  @Post('by-url')
  addByUrl(@Req() req: AuthReq, @Body() body: { url: string; city?: string; state?: string; neighborhood?: string }) {
    return this.productsService.addByUrl(body.url, req.user.userId, {
      city: body.city,
      state: body.state,
      neighborhood: body.neighborhood,
    });
  }

  @Get()
  findAll(@Req() req: AuthReq) {
    return this.productsService.findAllByUser(req.user.userId);
  }

  @Get('quota')
  getQuotaSummary(@Req() req: AuthReq) {
    return this.productsService.getQuotaSummary(req.user.userId);
  }

  @Get(':id')
  findOne(@Param('id') id: string) {
    return this.productsService.findOne(id);
  }

  @Delete(':id')
  remove(@Req() req: AuthReq, @Param('id') id: string) {
    return this.productsService.removeFromUser(id, req.user.userId);
  }

  @Patch(':id')
  update(@Param('id') id: string, @Body() body: UpdateProductDto) {
    return this.productsService.update(id, body);
  }

  @Post()
  create(@Body() body: CreateProductDto) {
    return this.productsService.create(body);
  }
}
