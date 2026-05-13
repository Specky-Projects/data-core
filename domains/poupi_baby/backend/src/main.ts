// IMPORTANTE: instrument.ts deve ser o primeiro import — inicializa o Sentry
// antes de qualquer outro módulo (necessário para traces de performance).
import './instrument';
import 'dotenv/config';

import { ValidationPipe } from '@nestjs/common';
import { NestFactory } from '@nestjs/core';
import { AppModule } from './app.module';
import { SentryExceptionFilter } from './common/sentry.filter';

async function bootstrap() {
  const app = await NestFactory.create(AppModule);

  app.enableCors({
    origin: process.env.FRONTEND_URL || 'http://localhost:3000',
    credentials: true,
  });

  app.useGlobalPipes(
    new ValidationPipe({
      whitelist: true,
      forbidNonWhitelisted: true,
      transform: true,
    }),
  );

  // Filtro global: captura exceções 5xx e envia ao Sentry
  app.useGlobalFilters(new SentryExceptionFilter());

  const port = parseInt(process.env.PORT ?? '3001', 10);
  await app.listen(port);
  console.log(`[Bootstrap] API rodando em http://localhost:${port}`);
}

bootstrap();
