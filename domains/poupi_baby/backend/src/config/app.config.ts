import { registerAs } from '@nestjs/config';

export const appConfig = registerAs('app', () => ({
  nodeEnv:     process.env.NODE_ENV     ?? 'development',
  port:        parseInt(process.env.PORT ?? '3001', 10),
  frontendUrl: process.env.FRONTEND_URL ?? 'http://localhost:3000',
}));

export const redisConfig = registerAs('redis', () => ({
  url: process.env.REDIS_URL ?? 'redis://localhost:6379',
}));

export const aiConfig = registerAs('ai', () => ({
  provider:   process.env.AI_PROVIDER   ?? 'mock',
  openaiKey:  process.env.OPENAI_API_KEY,
  claudeKey:  process.env.CLAUDE_API_KEY,
  maxTokens:  parseInt(process.env.AI_MAX_TOKENS ?? '1024', 10),
}));

export const featureFlags = registerAs('features', () => ({
  aiOps:       process.env.FEATURE_AI_OPS       === 'true',
  reviewIntel: process.env.FEATURE_REVIEW_INTEL === 'true',
  marketIntel: process.env.FEATURE_MARKET_INTEL === 'true',
}));

export const affiliateConfig = registerAs('affiliates', () => ({
  amazonTag:   process.env.AMAZON_AFFILIATE_TAG,
  mlClientId:  process.env.ML_CLIENT_ID,
  magaluToken: process.env.MAGALU_AFFILIATE_TOKEN,
}));
