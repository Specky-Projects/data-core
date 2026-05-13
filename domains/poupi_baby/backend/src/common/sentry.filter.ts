/**
 * sentry.filter.ts
 *
 * Exception filter global que:
 *  1. Captura exceções não tratadas e envia ao Sentry
 *  2. Adiciona contexto: userId, requestId, marketplace, stack
 *  3. Responde com JSON padronizado ao cliente
 */

import {
  ArgumentsHost,
  Catch,
  ExceptionFilter,
  HttpException,
  HttpStatus,
  Logger,
} from '@nestjs/common';
import * as Sentry from '@sentry/nestjs';
import { Request, Response } from 'express';

@Catch()
export class SentryExceptionFilter implements ExceptionFilter {
  private readonly logger = new Logger(SentryExceptionFilter.name);

  catch(exception: unknown, host: ArgumentsHost) {
    const ctx  = host.switchToHttp();
    const req  = ctx.getRequest<Request>();
    const res  = ctx.getResponse<Response>();

    const status =
      exception instanceof HttpException
        ? exception.getStatus()
        : HttpStatus.INTERNAL_SERVER_ERROR;

    const message =
      exception instanceof HttpException
        ? exception.message
        : 'Internal server error';

    // Não envia 4xx ao Sentry (erros de cliente, não de servidor)
    const shouldReport = status >= 500;

    if (shouldReport) {
      Sentry.withScope((scope) => {
        scope.setTag('url', req.url);
        scope.setTag('method', req.method);
        scope.setExtra('body', req.body);
        scope.setExtra('query', req.query);

        if (req.user) {
          const user = req.user as any;
          scope.setUser({ id: user.sub ?? user.id, email: user.email });
        }

        Sentry.captureException(exception);
      });

      this.logger.error(
        `[${req.method}] ${req.url} → ${status}`,
        exception instanceof Error ? exception.stack : String(exception),
      );
    }

    res.status(status).json({
      statusCode: status,
      message,
      timestamp: new Date().toISOString(),
      path: req.url,
    });
  }
}
