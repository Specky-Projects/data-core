import {
  Body,
  Controller,
  ForbiddenException,
  Get,
  Headers,
  Post,
  Patch,
  Req,
  UseGuards,
} from '@nestjs/common';

import { Request } from 'express';

import { AuthGuard } from '@nestjs/passport';

import { AuthService } from './auth.service';
import { SignupDto } from './dto/signup.dto';
import { LoginDto } from './dto/login.dto';
import { GoogleAuthDto } from './dto/google-auth.dto';

interface AuthenticatedRequest extends Request {
  user: { userId: string; email: string; role: string };
}

@Controller('auth')
export class AuthController {

  constructor(
    private authService: AuthService,
  ) {}

  @Post('signup')
  signup(
    @Body() data: SignupDto,
  ) {
    return this.authService.signup(data);
  }

  @Post('login')
  login(@Body() data: LoginDto) {
    return this.authService.login(data);
  }

  @Post('google')
  googleAuth(@Body() data: GoogleAuthDto) {
    return this.authService.googleAuth(data);
  }

  /** Sync interno Next.js → NestJS (server-to-server, sem exposição ao cliente) */
  @Post('sync')
  syncOAuth(
    @Headers('x-internal-secret') secret: string,
    @Body('email') email: string,
    @Body('name') name: string,
  ) {
    if (!secret || secret !== process.env.INTERNAL_SECRET) {
      throw new ForbiddenException('Acesso negado');
    }
    if (!email) throw new ForbiddenException('Email obrigatório');
    return this.authService.syncOAuthUser(email, name ?? '');
  }

  // BUG-14: decorators agrupados corretamente
  @UseGuards(AuthGuard('jwt'))
  @Get('me')
  me(@Req() req: AuthenticatedRequest) {
    return req.user;
  }

  @UseGuards(AuthGuard('jwt'))
  @Get('profile')
  profile(@Req() req: AuthenticatedRequest) {
    return this.authService.getProfile(req.user.userId);
  }

  @UseGuards(AuthGuard('jwt'))
  @Patch('profile')
  updateProfile(
    @Req() req: AuthenticatedRequest,
    @Body() data: { name?: string; email?: string; phone?: string | null },
  ) {
    return this.authService.updateProfile(req.user.userId, data);
  }

  @UseGuards(AuthGuard('jwt'))
  @Patch('password')
  updatePassword(
    @Req() req: AuthenticatedRequest,
    @Body() data: { currentPassword: string; newPassword: string },
  ) {
    return this.authService.updatePassword(req.user.userId, data.currentPassword, data.newPassword);
  }

  @UseGuards(AuthGuard('jwt'))
  @Post('email-confirmation/request')
  requestEmailConfirmation(@Req() req: AuthenticatedRequest) {
    return this.authService.requestEmailConfirmation(req.user.userId);
  }

  @UseGuards(AuthGuard('jwt'))
  @Post('email-confirmation/confirm')
  confirmEmail(
    @Req() req: AuthenticatedRequest,
    @Body('code') code: string,
  ) {
    return this.authService.confirmEmail(req.user.userId, code);
  }
}
