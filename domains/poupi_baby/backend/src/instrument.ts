/**
 * instrument.ts
 *
 * Inicialização do Sentry — deve ser o PRIMEIRO import do main.ts.
 * O Sentry precisa ser carregado antes de qualquer outro módulo para
 * interceptar corretamente as traces de performance (OpenTelemetry).
 */

import * as Sentry from '@sentry/nestjs';
import { nodeProfilingIntegration } from '@sentry/profiling-node';

const dsn = process.env.SENTRY_DSN;

Sentry.init({
  dsn,
  enabled: !!dsn,
  environment: process.env.NODE_ENV ?? 'development',

  // Traces de performance — 20% em prod, 100% em dev
  tracesSampleRate: process.env.NODE_ENV === 'production' ? 0.2 : 1.0,

  // Profiling de CPU (flamegraphs) — requer @sentry/profiling-node
  profilesSampleRate: process.env.NODE_ENV === 'production' ? 0.1 : 1.0,

  integrations: [
    nodeProfilingIntegration(),
  ],

  // Não loga dados sensíveis
  beforeSend(event) {
    // Remove cookies e headers de autenticação
    if (event.request?.cookies) delete event.request.cookies;
    if (event.request?.headers?.authorization) {
      event.request.headers.authorization = '[Filtered]';
    }
    return event;
  },

  // Ignora erros esperados (404, 401, 403)
  ignoreErrors: [
    'NotFoundException',
    'UnauthorizedException',
    'ForbiddenException',
  ],
});
