/**
 * cache.service.ts
 *
 * Serviço de cache Redis com quatro responsabilidades:
 *
 *  1. Cache de preços por URL
 *     Evita scraping duplicado quando múltiplos usuários
 *     monitoram o mesmo produto. TTL configurável por domínio.
 *
 *  2. Cache de preços por chave determinística (store:externalId) — P4
 *     Independente de UTM params ou variações de URL.
 *     TTL inteligente por marketplace (frescor diferenciado).
 *
 *  3. Rate Limiter (Token Bucket) por domínio
 *     Controla o número de requisições por segundo para cada
 *     marketplace, prevenindo bloqueios por bot-detection.
 *     Usa script Lua para operação atômica no Redis.
 *
 *  4. Blacklist de tokens JWT
 *     Invalida tokens antes da expiração natural (logout, revogação).
 *
 * Fallback gracioso: todas as operações funcionam sem Redis
 * (cache miss, rate limit liberado, token não blacklisted).
 */

import { Injectable, Logger, OnModuleDestroy, OnModuleInit } from '@nestjs/common';
import { createClient, RedisClientType } from 'redis';
import * as crypto from 'crypto';

// ---------------------------------------------------------------------------
// TTL inteligente por marketplace (em segundos)
//
//   amazon       → 4h   (preços mudam <10x/dia; ASIN estável)
//   mercadolivre → 2h   (dinâmica mais alta; vendedores competindo)
//   kabum        → 6h   (B2C estável; promoções pontuais)
//   magalu       → 4h   (mix de oferta diária e semanal)
//   drogasil     → 8h   (preços de farmácia mudam pouco)
//   default      → 3h   (marketplaces desconhecidos)
// ---------------------------------------------------------------------------

const MARKETPLACE_TTL_SECS: Record<string, number> = {
  amazon:       4 * 3600,   // 4h
  mercadolivre: 2 * 3600,   // 2h
  kabum:        6 * 3600,   // 6h
  magalu:       4 * 3600,   // 4h
  drogasil:     8 * 3600,   // 8h
  drogaraia:    8 * 3600,   // 8h
  default:      3 * 3600,   // 3h
};

// ---------------------------------------------------------------------------
// Rate limits por domínio (tokens/segundo)
// ---------------------------------------------------------------------------

const DOMAIN_RATE_LIMITS: Record<string, { tokensPerSecond: number; maxTokens: number }> = {
  'amazon.com.br':        { tokensPerSecond: 0.1,  maxTokens: 1 },
  'mercadolivre.com.br':  { tokensPerSecond: 0.2,  maxTokens: 2 },
  'shopee.com.br':        { tokensPerSecond: 0.1,  maxTokens: 1 },
  'magazineluiza.com.br': { tokensPerSecond: 0.14, maxTokens: 1 },
  'magalu.com':           { tokensPerSecond: 0.14, maxTokens: 1 },
  'americanas.com.br':    { tokensPerSecond: 0.12, maxTokens: 1 },
  'kabum.com.br':         { tokensPerSecond: 0.14, maxTokens: 1 },
  'drogasil.com.br':      { tokensPerSecond: 0.14, maxTokens: 1 },
  'drogaraia.com.br':     { tokensPerSecond: 0.14, maxTokens: 1 },
  'paguemenos.com.br':    { tokensPerSecond: 0.14, maxTokens: 1 },
  default:                { tokensPerSecond: 0.12, maxTokens: 1 },
};

// Script Lua para token bucket atômico no Redis
const TOKEN_BUCKET_LUA = `
local key       = KEYS[1]
local now       = tonumber(ARGV[1])
local rate      = tonumber(ARGV[2])
local maxTokens = tonumber(ARGV[3])
local current   = redis.call('HGETALL', key)
local tokens, lastTime

if #current == 0 then
  tokens   = maxTokens
  lastTime = now
else
  local data = {}
  for i = 1, #current, 2 do data[current[i]] = tonumber(current[i+1]) end
  tokens   = data['tokens']   or maxTokens
  lastTime = data['lastTime'] or now
end

local elapsed  = math.max(0, now - lastTime) / 1000
local refill   = elapsed * rate
tokens = math.min(maxTokens, tokens + refill)

if tokens >= 1 then
  tokens = tokens - 1
  redis.call('HSET', key, 'tokens', tokens, 'lastTime', now)
  redis.call('EXPIRE', key, 3600)
  return 1
else
  redis.call('HSET', key, 'tokens', tokens, 'lastTime', now)
  redis.call('EXPIRE', key, 3600)
  return 0
end
`;

// ---------------------------------------------------------------------------
// Serviço
// ---------------------------------------------------------------------------

@Injectable()
export class CacheService implements OnModuleInit, OnModuleDestroy {
  private readonly logger = new Logger(CacheService.name);
  private client: RedisClientType | null = null;
  private available = false;

  async onModuleInit() {
    const url = process.env.REDIS_URL || 'redis://localhost:6379';
    try {
      this.client = createClient({
        url,
        socket: { reconnectStrategy: false }, // sem retry automático
      }) as RedisClientType;

      // Loga erro apenas uma vez
      this.client.on('error', () => {
        if (this.available) {
          this.logger.warn('Redis indisponível — operando sem cache');
          this.available = false;
        }
      });

      await this.client.connect();
      this.available = true;
      this.logger.log(`Redis conectado: ${url}`);
    } catch {
      this.logger.warn('Redis não encontrado — fallback gracioso ativo (sem cache)');
      this.available = false;
    }
  }

  async onModuleDestroy() {
    if (this.client) await this.client.disconnect();
  }

  get isAvailable(): boolean {
    return this.available;
  }

  // -------------------------------------------------------------------------
  // Helpers internos
  // -------------------------------------------------------------------------

  private urlKey(url: string): string {
    const hash = crypto.createHash('md5').update(url).digest('hex').slice(0, 16);
    return `price:v1:${hash}`;
  }

  /**
   * Chave determinística por store + externalId.
   * Independente de UTM params ou variações de URL.
   * Formato: price:v2:amazon:B09XXXXX12
   */
  static productKey(store: string, externalId: string): string {
    return `price:v2:${store}:${externalId}`;
  }

  /**
   * TTL inteligente por marketplace.
   * Produtos de marketplaces com preços mais voláteis têm TTL menor.
   */
  static ttlForStore(store: string): number {
    const key = store.toLowerCase();
    // Busca match parcial (ex: "amazon.com.br" → "amazon")
    for (const [prefix, ttl] of Object.entries(MARKETPLACE_TTL_SECS)) {
      if (prefix !== 'default' && key.includes(prefix)) return ttl;
    }
    return MARKETPLACE_TTL_SECS.default;
  }

  private domainOf(url: string): string {
    try { return new URL(url).hostname.replace('www.', ''); } catch { return 'unknown'; }
  }

  private rateLimitConfig(domain: string) {
    return DOMAIN_RATE_LIMITS[domain] ?? DOMAIN_RATE_LIMITS.default;
  }

  // -------------------------------------------------------------------------
  // Cache de preços por URL
  // -------------------------------------------------------------------------

  /**
   * Retorna o preço cacheado para a URL, ou null se expirado/ausente.
   */
  async getCachedPrice(url: string): Promise<number | null> {
    if (!this.available || !this.client) return null;
    try {
      const raw = await this.client.get(this.urlKey(url));
      return raw ? parseFloat(raw) : null;
    } catch { return null; }
  }

  async setCachedPrice(url: string, price: number, ttlSecs = 300): Promise<void> {
    if (!this.available || !this.client) return;
    try {
      await this.client.set(this.urlKey(url), price.toString(), { EX: ttlSecs });
    } catch { /* falha silenciosa */ }
  }

  async invalidateCache(url: string): Promise<void> {
    if (!this.available || !this.client) return;
    try { await this.client.del(this.urlKey(url)); } catch { /* */ }
  }

  // -------------------------------------------------------------------------
  // Cache por chave determinística (P4 — store:externalId)
  // Resolve o problema de mesmo produto com URLs diferentes.
  // -------------------------------------------------------------------------

  async getByKey(key: string): Promise<number | null> {
    if (!this.available || !this.client) return null;
    try {
      const raw = await this.client.get(key);
      return raw ? parseFloat(raw) : null;
    } catch { return null; }
  }

  async setByKey(key: string, price: number, ttlSecs?: number): Promise<void> {
    if (!this.available || !this.client) return;
    // Se o chamador não especificar TTL, infere pelo store na chave
    // Formato esperado: price:v2:<store>:<externalId>
    const effectiveTtl = ttlSecs ?? (() => {
      const parts = key.split(':');
      const store = parts[2] ?? '';
      return CacheService.ttlForStore(store);
    })();
    try {
      await this.client.set(key, price.toString(), { EX: effectiveTtl });
    } catch { /* */ }
  }

  async delByKey(key: string): Promise<void> {
    if (!this.available || !this.client) return;
    try { await this.client.del(key); } catch { /* */ }
  }

  /**
   * Invalida todas as chaves de um produto num marketplace específico.
   * Útil quando um admin força re-sync manual.
   * Padrão: price:v2:<store>:<externalId>
   */
  async invalidateProduct(store: string, externalId: string): Promise<void> {
    const key = CacheService.productKey(store, externalId);
    await this.delByKey(key);
  }

  // -------------------------------------------------------------------------
  // Rate Limiter
  // -------------------------------------------------------------------------

  /**
   * Tenta adquirir um token para o domínio da URL.
   * Se não houver tokens disponíveis e `wait=true`, aguarda até `maxWaitMs`.
   *
   * @returns true se o request pode prosseguir
   */
  async acquireRateLimit(url: string, wait = true, maxWaitMs = 30_000): Promise<boolean> {
    if (!this.available || !this.client) return true; // sem Redis → libera

    const domain = this.domainOf(url);
    const { tokensPerSecond, maxTokens } = this.rateLimitConfig(domain);
    const key = `ratelimit:${domain}`;
    const intervalMs = 1000 / tokensPerSecond;

    const tryAcquire = async (): Promise<boolean> => {
      try {
        const result = await (this.client as RedisClientType).eval(TOKEN_BUCKET_LUA, {
          keys: [key],
          arguments: [Date.now().toString(), tokensPerSecond.toString(), maxTokens.toString()],
        });
        return result === 1;
      } catch { return true; }
    };

    if (await tryAcquire()) return true;
    if (!wait) return false;

    // Aguarda slots com polling
    const start = Date.now();
    while (Date.now() - start < maxWaitMs) {
      await new Promise((r) => setTimeout(r, intervalMs));
      if (await tryAcquire()) return true;
    }

    this.logger.warn(`Rate limit esgotado para ${domain} após ${maxWaitMs}ms`);
    return false;
  }

  // -------------------------------------------------------------------------
  // Blacklist JWT
  // -------------------------------------------------------------------------

  async blacklistToken(token: string, expiresInSecs: number): Promise<void> {
    if (!this.available || !this.client) return;
    const hash = crypto.createHash('sha256').update(token).digest('hex');
    try {
      await this.client.set(`jwt:blacklist:${hash}`, '1', { EX: expiresInSecs });
    } catch { /* */ }
  }

  async isTokenBlacklisted(token: string): Promise<boolean> {
    if (!this.available || !this.client) return false;
    const hash = crypto.createHash('sha256').update(token).digest('hex');
    try {
      return (await this.client.exists(`jwt:blacklist:${hash}`)) === 1;
    } catch { return false; }
  }

  // -------------------------------------------------------------------------
  // Utilitários de diagnóstico
  // -------------------------------------------------------------------------

  /**
   * Retorna métricas básicas do Redis para o dashboard operacional.
   */
  async getInfo(): Promise<{ available: boolean; usedMemory?: string; connectedClients?: number }> {
    if (!this.available || !this.client) return { available: false };
    try {
      const info = await this.client.info('memory');
      const usedMemory = info.match(/used_memory_human:(\S+)/)?.[1];
      const clientsInfo = await this.client.info('clients');
      const connectedClients = parseInt(clientsInfo.match(/connected_clients:(\d+)/)?.[1] ?? '0', 10);
      return { available: true, usedMemory, connectedClients };
    } catch {
      return { available: true };
    }
  }
}
