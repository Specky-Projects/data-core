import {
  Body,
  Controller,
  DefaultValuePipe,
  Get,
  Param,
  ParseIntPipe,
  Patch,
  Post,
  Query,
  Request,
  UseGuards,
} from '@nestjs/common';
import { AuthGuard } from '@nestjs/passport';
import { AdminGuard } from '../common/admin.guard';
import { AdminService } from './admin.service';
import { PromotionsService } from '../promotions/promotions.service';
import { AdminListQueryDto, UpdateUserRoleDto } from './dto/admin-query.dto';

@Controller('admin')
@UseGuards(AuthGuard('jwt'), AdminGuard)
export class AdminController {
  constructor(
    private readonly admin: AdminService,
    private readonly promotions: PromotionsService,
  ) {}

  @Get('me')
  me(@Request() req: any) {
    return { userId: req.user.userId, email: req.user.email, role: req.user.role };
  }

  @Get('overview')
  overview() {
    return this.admin.overview();
  }

  @Get('products')
  products(@Query() query: AdminListQueryDto) {
    return this.admin.products(query);
  }

  @Get('products/:id')
  productDetail(@Param('id') id: string) {
    return this.admin.productDetail(id);
  }

  @Patch('products/:id/active')
  setProductActive(@Param('id') id: string, @Body('active') active: boolean, @Request() req: any) {
    return this.admin.setProductActive(id, !!active, req.user.userId);
  }

  @Get('offers')
  offers(@Query() query: AdminListQueryDto) {
    return this.admin.offers(query);
  }

  @Get('marketplaces')
  marketplaces() {
    return this.admin.marketplaces();
  }

  @Get('users')
  users(@Query() query: AdminListQueryDto) {
    return this.admin.users(query);
  }

  @Patch('users/:id/role')
  updateUserRole(@Param('id') id: string, @Body() body: UpdateUserRoleDto, @Request() req: any) {
    return this.admin.updateUserRole(id, body.role, req.user.userId);
  }

  @Patch('users/:id/block')
  blockUser(@Param('id') id: string, @Body('blocked') blocked: boolean, @Request() req: any) {
    return this.admin.blockUser(id, !!blocked, req.user.userId);
  }

  @Get('alerts')
  alerts(@Query() query: AdminListQueryDto) {
    return this.admin.alerts(query);
  }

  @Get('scraping')
  scraping() {
    return this.admin.scraping();
  }

  @Post('scraping/retry-failed')
  retryFailed(@Request() req: any) {
    return this.admin.retryFailedJobs(req.user.userId);
  }

  @Post('scraping/pause')
  pauseScraping(@Request() req: any) {
    return this.admin.pauseScraping(req.user.userId);
  }

  @Post('scraping/resume')
  resumeScraping(@Request() req: any) {
    return this.admin.resumeScraping(req.user.userId);
  }

  @Post('scraping/proxies/reset')
  resetProxyCooldowns(@Body('source') source: string | undefined, @Request() req: any) {
    return this.admin.resetProxyCooldowns(source, req.user.userId);
  }

  @Post('scraping/circuit/:source/open')
  openCircuit(
    @Param('source') source: string,
    @Body('minutes', new DefaultValuePipe(30), ParseIntPipe) minutes: number,
    @Request() req: any,
  ) {
    return this.admin.openCircuit(source, minutes, req.user.userId);
  }

  @Post('scraping/circuit/:source/close')
  closeCircuit(@Param('source') source: string, @Request() req: any) {
    return this.admin.closeCircuit(source, req.user.userId);
  }

  @Get('jobs')
  jobs() {
    return this.admin.scraping();
  }

  @Get('analytics')
  analytics(@Query('days', new DefaultValuePipe(30), ParseIntPipe) days: number) {
    return this.admin.analyticsOverview(days);
  }

  @Get('logs')
  logs(@Query() query: AdminListQueryDto) {
    return this.admin.logs(query);
  }

  @Get('scraping/logs')
  scrapingLogs(@Query() query: AdminListQueryDto) {
    return this.admin.scrapingLogs(query);
  }

  @Get('settings')
  settings() {
    return this.admin.settings();
  }

  @Post('promotions/telegram-radar')
  telegramRadar(
    @Body('dryRun', new DefaultValuePipe(true)) dryRun: boolean,
    @Body('limit', new DefaultValuePipe(5), ParseIntPipe) limit: number,
    @Body('chatId') chatId?: string,
  ) {
    return this.promotions.publishRadar({ dryRun: dryRun !== false, limit, chatId });
  }

  @Get('promotions/telegram-radar')
  telegramRadarHistory(@Query('limit', new DefaultValuePipe(30), ParseIntPipe) limit: number) {
    return this.promotions.recentTelegramPosts(limit);
  }
}
