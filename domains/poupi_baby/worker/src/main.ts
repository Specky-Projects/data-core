/**
 * Worker standalone — processa a fila BullMQ sem servidor HTTP.
 *
 * Arquitetura:
 *   Backend API  →  Redis/BullMQ  ←  Worker (este processo)
 *
 * O worker:
 *   - Conecta ao mesmo Redis que a API
 *   - Consome jobs da fila 'scraper'
 *   - Usa o mesmo CrawlerService (compartilhado via symlink ou monorepo)
 *   - Pode rodar em múltiplas instâncias (horizontally scalable)
 *   - Reinicia independentemente da API
 */

import './instrument'; // Sentry — DEVE ser o primeiro import
import 'dotenv/config';

import { NestFactory } from '@nestjs/core';
import { WorkerModule } from './worker.module';
import { Logger } from '@nestjs/common';

const logger = new Logger('Worker');

async function bootstrap() {
  // NestJS sem HTTP — apenas o worker BullMQ
  const app = await NestFactory.createApplicationContext(WorkerModule, {
    logger: ['log', 'error', 'warn'],
  });

  // Graceful shutdown
  process.on('SIGTERM', async () => {
    logger.log('SIGTERM recebido — encerrando worker graciosamente...');
    await app.close();
    process.exit(0);
  });

  process.on('SIGINT', async () => {
    logger.log('SIGINT recebido — encerrando worker graciosamente...');
    await app.close();
    process.exit(0);
  });

  logger.log('Worker iniciado — aguardando jobs na fila...');
}

bootstrap().catch((err) => {
  console.error('Falha ao iniciar worker:', err);
  process.exit(1);
});
