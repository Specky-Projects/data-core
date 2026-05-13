import { Global, Module } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { validateEnv } from './env.schema';
import {
  appConfig,
  redisConfig,
  aiConfig,
  featureFlags,
  affiliateConfig,
} from './app.config';

/**
 * ConfigModule global — disponível em toda a aplicação sem reimportar.
 * Valida as variáveis de ambiente no bootstrap via Zod.
 */
@Global()
@Module({
  imports: [
    ConfigModule.forRoot({
      isGlobal:    true,
      validate:    validateEnv,
      cache:       true,           // evita re-parsear em cada injeção
      load: [
        appConfig,
        redisConfig,
        aiConfig,
        featureFlags,
        affiliateConfig,
      ],
    }),
  ],
})
export class AppConfigModule {}
