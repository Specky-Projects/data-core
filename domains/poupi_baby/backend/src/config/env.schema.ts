import { z } from 'zod';

/**
 * Schema de validação de todas as variáveis de ambiente.
 * Falha no bootstrap se alguma variável obrigatória estiver ausente ou inválida.
 * Nenhum módulo deve acessar process.env diretamente — usar ConfigService.
 */
export const EnvSchema = z.object({
  // ── App ──────────────────────────────────────────────────────────────
  NODE_ENV:  z.enum(['development', 'production', 'test']).default('development'),
  PORT:      z.coerce.number().min(1).max(65535).default(3001),

  // ── Banco de dados ───────────────────────────────────────────────────
  DATABASE_URL: z.string().min(1, 'DATABASE_URL é obrigatório'),

  // ── Redis ────────────────────────────────────────────────────────────
  REDIS_URL: z.string().default('redis://localhost:6379'),

  // ── Auth ─────────────────────────────────────────────────────────────
  JWT_SECRET:      z.string().min(16, 'JWT_SECRET deve ter pelo menos 16 chars'),
  JWT_EXPIRES_IN:  z.string().default('7d'),
  NEXTAUTH_SECRET: z.string().optional(),

  // ── OAuth (opcional) ─────────────────────────────────────────────────
  GOOGLE_CLIENT_ID:     z.string().optional(),
  GOOGLE_CLIENT_SECRET: z.string().optional(),

  // ── Pagamentos (opcional) ────────────────────────────────────────────
  MERCADOPAGO_TOKEN:     z.string().optional(),
  STRIPE_SECRET:         z.string().optional(),
  STRIPE_WEBHOOK_SECRET: z.string().optional(),

  // ── E-mail (opcional) ────────────────────────────────────────────────
  GMAIL_USER:     z.string().email().optional(),
  GMAIL_PASSWORD: z.string().optional(),

  // ── Scraping / Worker ────────────────────────────────────────────────
  WORKER_CONCURRENCY: z.coerce.number().min(1).max(50).default(5),

  // ── Observabilidade ──────────────────────────────────────────────────
  SENTRY_DSN:       z.string().url().optional().or(z.literal('')),
  FRONTEND_URL:     z.string().url().optional().or(z.literal('')).default('http://localhost:3000'),

  // ── IA ───────────────────────────────────────────────────────────────
  AI_PROVIDER:    z.enum(['openai', 'claude', 'mock']).default('mock'),
  OPENAI_API_KEY: z.string().optional(),
  CLAUDE_API_KEY: z.string().optional(),
  AI_MAX_TOKENS:  z.coerce.number().default(1024),

  // ── Feature Flags ────────────────────────────────────────────────────
  FEATURE_AI_OPS:        z.coerce.boolean().default(false),
  FEATURE_REVIEW_INTEL:  z.coerce.boolean().default(false),
  FEATURE_MARKET_INTEL:  z.coerce.boolean().default(false),

  // ── Afiliados (opcional) ─────────────────────────────────────────────
  AMAZON_AFFILIATE_TAG:   z.string().optional(),
  ML_CLIENT_ID:           z.string().optional(),
  ML_CLIENT_SECRET:       z.string().optional(),
  MAGALU_AFFILIATE_TOKEN: z.string().optional(),

  // ── Backups (opcional) ───────────────────────────────────────────────
  BACKUP_RETENTION_DAYS: z.coerce.number().default(30),
});

export type Env = z.infer<typeof EnvSchema>;

/**
 * Valida as variáveis de ambiente no bootstrap.
 * Exibe erros detalhados e encerra o processo se inválido.
 */
export function validateEnv(config: Record<string, unknown>): Env {
  const result = EnvSchema.safeParse(config);

  if (!result.success) {
    console.error('\n❌ Validação de variáveis de ambiente falhou:\n');
    result.error.issues.forEach((e) => {
      const path = e.path.join('.');
      console.error(`  ${path ? path + ': ' : ''}${e.message}`);
    });
    console.error('\nVerifique o arquivo .env e tente novamente.\n');
    process.exit(1);
  }

  return result.data;
}
