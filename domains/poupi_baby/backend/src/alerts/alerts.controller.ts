import {
  Body,
  Controller,
  Delete,
  Get,
  Param,
  Post,
  Req,
  UseGuards,
} from '@nestjs/common';

import { Request } from 'express';

import { AuthGuard } from '@nestjs/passport';

import { AlertsService } from './alerts.service';

import { CreateAlertDto } from './dto/create-alert.dto';

interface AuthenticatedRequest extends Request {
  user: { userId: string; email: string };
}

// BUG-14: @UseGuards aplicado diretamente no controller (não separado)
@UseGuards(AuthGuard('jwt'))
@Controller('alerts')
export class AlertsController {

  constructor(
    private readonly alertsService: AlertsService,
  ) {}

  @Post()
  create(
    @Body() data: CreateAlertDto,
    @Req() req: AuthenticatedRequest,
  ) {
    return this.alertsService.create(data, req.user.userId);
  }

  @Get('my-alerts')
  myAlerts(@Req() req: AuthenticatedRequest) {
    return this.alertsService.myAlerts(req.user.userId);
  }

  @Post('watchlist/:productId')
  watch(
    @Param('productId') productId: string,
    @Req() req: AuthenticatedRequest,
  ) {
    return this.alertsService.watch(productId, req.user.userId);
  }

  @Get('watchlist')
  myWatchlist(@Req() req: AuthenticatedRequest) {
    return this.alertsService.myWatchlist(req.user.userId);
  }

  @Delete('watchlist/:productId')
  unwatch(
    @Param('productId') productId: string,
    @Req() req: AuthenticatedRequest,
  ) {
    return this.alertsService.unwatch(productId, req.user.userId);
  }

  @Delete(':id')
  cancel(
    @Param('id') id: string,
    @Req() req: AuthenticatedRequest,
  ) {
    return this.alertsService.cancel(id, req.user.userId);
  }
}
