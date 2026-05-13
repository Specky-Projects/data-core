import { CanActivate, ExecutionContext, ForbiddenException, Injectable } from '@nestjs/common';

/**
 * AdminGuard — exige role === 'admin' no JWT.
 * Usar após AuthGuard('jwt'):
 *
 *   @UseGuards(AuthGuard('jwt'), AdminGuard)
 */
@Injectable()
export class AdminGuard implements CanActivate {
  canActivate(ctx: ExecutionContext): boolean {
    const req  = ctx.switchToHttp().getRequest();
    const user = req.user as { role?: string } | undefined;

    if (user?.role !== 'admin') {
      throw new ForbiddenException('Acesso restrito a administradores.');
    }
    return true;
  }
}
