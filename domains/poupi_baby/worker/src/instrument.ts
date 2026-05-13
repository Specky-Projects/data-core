import * as Sentry from '@sentry/nestjs';
import { nodeProfilingIntegration } from '@sentry/profiling-node';

Sentry.init({
  dsn:         process.env.SENTRY_DSN,
  enabled:     !!process.env.SENTRY_DSN,
  environment: process.env.NODE_ENV ?? 'development',
  tracesSampleRate:  process.env.NODE_ENV === 'production' ? 0.2 : 1.0,
  profilesSampleRate: 0.1,
  integrations: [nodeProfilingIntegration()],
  // Tag para diferenciar erros do worker vs API no Sentry
  initialScope: { tags: { service: 'worker' } },
});
