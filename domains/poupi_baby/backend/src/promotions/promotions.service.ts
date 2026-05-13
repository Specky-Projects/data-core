import { createHash } from 'crypto';
import { Injectable, Logger } from '@nestjs/common';
import { PrismaService } from '../prisma/prisma.service';
import { AffiliateService } from '../affiliate/affiliate.service';

const DEFAULT_MIN_SCORE = 0.62;
const DEFAULT_COOLDOWN_HOURS = 24;

type RadarOptions = {
  dryRun?: boolean;
  limit?: number;
  chatId?: string;
  minScore?: number;
};

type RadarCandidate = {
  offer: any;
  currentPrice: number;
  previousPrice: number | null;
  avgPrice: number | null;
  historicalMin: number | null;
  bestMarketPrice: number | null;
  worstMarketPrice: number | null;
  discountVsAvg: number;
  discountVsOriginal: number;
  spreadSavings: number;
  score: number;
  reasons: string[];
  message: string;
  messageHash: string;
};

@Injectable()
export class PromotionsService {
  private readonly logger = new Logger(PromotionsService.name);

  constructor(
    private prisma: PrismaService,
    private affiliateService: AffiliateService,
  ) {}

  async publishRadar(options: RadarOptions = {}) {
    const dryRun = options.dryRun ?? false;
    const limit = Math.max(1, Math.min(options.limit ?? 5, 20));
    const minScore = options.minScore ?? Number(process.env.TELEGRAM_RADAR_MIN_SCORE ?? DEFAULT_MIN_SCORE);
    const chatId = options.chatId ?? process.env.TELEGRAM_CHAT_ID ?? process.env.TELEGRAM_CHANNEL_ID ?? '';

    const candidates = await this.findRadarCandidates(limit * 4);
    const selected = this.pickBestPerProduct(candidates)
      .filter((candidate) => candidate.score >= minScore)
      .sort((a, b) => b.score - a.score)
      .slice(0, limit);

    const result = {
      dryRun,
      analyzed: candidates.length,
      eligible: selected.length,
      sent: 0,
      skippedDuplicate: 0,
      skippedCooldown: 0,
      skippedConfig: 0,
      items: selected.map((candidate) => this.preview(candidate)),
    };

    for (const candidate of selected) {
      const cooldown = await this.hasRecentPost(candidate.offer.productId, chatId);
      if (cooldown) {
        result.skippedCooldown++;
        await this.logTelegramPost(candidate, chatId || 'dry-run', 'skipped', 'cooldown');
        continue;
      }

      const duplicate = await this.prisma.telegramPost.findFirst({
        where: { chatId: chatId || 'dry-run', messageHash: candidate.messageHash, status: 'sent' },
      });
      if (duplicate) {
        result.skippedDuplicate++;
        continue;
      }

      if (dryRun) continue;

      if (!chatId || !process.env.TELEGRAM_BOT_TOKEN) {
        result.skippedConfig++;
        await this.logTelegramPost(candidate, chatId || 'not-configured', 'skipped', 'telegram_not_configured');
        continue;
      }

      await this.sendTelegram(chatId, candidate.message);
      await this.logTelegramPost(candidate, chatId, 'sent');
      result.sent++;
    }

    return result;
  }

  async recentTelegramPosts(limit = 30) {
    const take = Math.max(1, Math.min(limit, 100));
    const posts = await this.prisma.telegramPost.findMany({
      orderBy: { sentAt: 'desc' },
      take,
    });

    return posts.map((post) => ({
      id: post.id,
      productId: post.productId,
      offerId: post.offerId,
      chatId: post.chatId,
      priceSnapshot: Number(post.priceSnapshot),
      score: post.score,
      status: post.status,
      reason: post.reason,
      sentAt: post.sentAt,
      payload: this.safeJson(post.payload),
    }));
  }

  // Backwards-compatible entry point for existing callers.
  async detectAndPublish() {
    return this.publishRadar({ dryRun: false });
  }

  private async findRadarCandidates(take: number): Promise<RadarCandidate[]> {
    const offers = await this.prisma.offer.findMany({
      where: {
        deletedAt: null,
        availability: true,
        product: { deletedAt: null },
        OR: [
          { currentPrice: { not: null } },
          { price: { gt: 0 } },
        ],
      },
      include: {
        marketplace: true,
        product: true,
        priceHistory: {
          orderBy: { capturedAt: 'desc' },
          take: 30,
        },
      },
      orderBy: [
        { lastValidScrapedAt: 'desc' },
        { updatedAt: 'desc' },
      ],
      take,
    });

    const productIds = Array.from(new Set(offers.map((offer) => offer.productId)));
    const marketOffers = await this.prisma.offer.findMany({
      where: {
        productId: { in: productIds },
        deletedAt: null,
        availability: true,
      },
      select: {
        productId: true,
        price: true,
        currentPrice: true,
      },
    });

    const byProduct = new Map<string, number[]>();
    for (const offer of marketOffers) {
      const price = this.priceOf(offer);
      if (!price) continue;
      byProduct.set(offer.productId, [...(byProduct.get(offer.productId) ?? []), price]);
    }

    return offers
      .map((offer) => this.toCandidate(offer, byProduct.get(offer.productId) ?? []))
      .filter((candidate): candidate is RadarCandidate => Boolean(candidate));
  }

  private toCandidate(offer: any, marketPrices: number[]): RadarCandidate | null {
    const currentPrice = this.priceOf(offer);
    if (!currentPrice) return null;

    const historyPrices = (offer.priceHistory ?? [])
      .map((entry) => Number(entry.price))
      .filter((price) => Number.isFinite(price) && price > 0);

    const previousPrice = historyPrices.find((price) => price !== currentPrice) ?? null;
    const avgPrice = historyPrices.length
      ? historyPrices.reduce((sum, price) => sum + price, 0) / historyPrices.length
      : null;
    const historicalMin = historyPrices.length ? Math.min(...historyPrices) : null;
    const bestMarketPrice = marketPrices.length ? Math.min(...marketPrices) : currentPrice;
    const worstMarketPrice = marketPrices.length ? Math.max(...marketPrices) : currentPrice;

    const original = offer.originalPrice ? Number(offer.originalPrice) : null;
    const discountVsAvg = avgPrice && avgPrice > currentPrice ? ((avgPrice - currentPrice) / avgPrice) * 100 : 0;
    const discountVsOriginal = original && original > currentPrice ? ((original - currentPrice) / original) * 100 : 0;
    const spreadSavings = worstMarketPrice && worstMarketPrice > currentPrice ? worstMarketPrice - currentPrice : 0;

    let score = 0;
    const reasons: string[] = [];

    if (discountVsAvg >= 8) {
      score += 0.28;
      reasons.push(`${Math.round(discountVsAvg)}% abaixo da media recente`);
    }
    if (discountVsOriginal >= 10) {
      score += 0.2;
      reasons.push(`${Math.round(discountVsOriginal)}% abaixo do preco original`);
    }
    if (bestMarketPrice === currentPrice && marketPrices.length > 1) {
      score += 0.18;
      reasons.push(`menor preco entre ${marketPrices.length} lojas`);
    }
    if (spreadSavings >= 5) {
      score += 0.14;
      reasons.push(`economia possivel de R$ ${spreadSavings.toFixed(2)}`);
    }
    if (historicalMin && currentPrice <= historicalMin * 1.03) {
      score += 0.14;
      reasons.push('perto do menor preco historico');
    }
    if (offer.pricePerUnit) {
      score += 0.06;
      reasons.push('comparacao por unidade disponivel');
    }

    if (!this.isPoupiBabyProduct(offer.product)) return null;
    if (score <= 0) return null;

    const roundedScore = Math.round(score * 100) / 100;
    const message = this.formatRadarMessage({
      offer,
      currentPrice,
      avgPrice,
      bestMarketPrice,
      worstMarketPrice,
      spreadSavings,
      reasons,
    });

    return {
      offer,
      currentPrice,
      previousPrice,
      avgPrice,
      historicalMin,
      bestMarketPrice,
      worstMarketPrice,
      discountVsAvg: Math.round(discountVsAvg * 10) / 10,
      discountVsOriginal: Math.round(discountVsOriginal * 10) / 10,
      spreadSavings: Math.round(spreadSavings * 100) / 100,
      score: roundedScore,
      reasons,
      message,
      messageHash: this.hash(`${offer.productId}:${offer.id}:${currentPrice.toFixed(2)}`),
    };
  }

  private pickBestPerProduct(candidates: RadarCandidate[]): RadarCandidate[] {
    const byProduct = new Map<string, RadarCandidate>();
    for (const candidate of candidates) {
      const existing = byProduct.get(candidate.offer.productId);
      if (!existing || candidate.score > existing.score) {
        byProduct.set(candidate.offer.productId, candidate);
      }
    }
    return Array.from(byProduct.values());
  }

  private formatRadarMessage(input: {
    offer: any;
    currentPrice: number;
    avgPrice: number | null;
    bestMarketPrice: number | null;
    worstMarketPrice: number | null;
    spreadSavings: number;
    reasons: string[];
  }): string {
    const { offer, currentPrice, avgPrice, spreadSavings, reasons } = input;
    const { affiliateUrl } = this.affiliateService.generateAffiliateUrl(offer.productUrl);
    const unitLine = offer.pricePerUnit
      ? `\nPreco por unidade: R$ ${Number(offer.pricePerUnit).toFixed(2)}`
      : '';
    const avgLine = avgPrice
      ? `\nMedia recente: R$ ${avgPrice.toFixed(2)}`
      : '';
    const savingsLine = spreadSavings > 0
      ? `\nEconomia vs maior oferta: ate R$ ${spreadSavings.toFixed(2)}`
      : '';

    return [
      'Radar Poupi Baby',
      '',
      offer.product.canonicalName ?? offer.product.title,
      `Melhor preco encontrado: R$ ${currentPrice.toFixed(2)}`,
      `Loja: ${offer.marketplace?.name ?? 'Loja monitorada'}`,
      unitLine.trim(),
      avgLine.trim(),
      savingsLine.trim(),
      '',
      `Por que entrou no radar: ${reasons.slice(0, 3).join('; ')}.`,
      '',
      `Ver oferta: ${affiliateUrl}`,
    ].filter(Boolean).join('\n');
  }

  private async hasRecentPost(productId: string, chatId: string): Promise<boolean> {
    if (!chatId) return false;
    const hours = Number(process.env.TELEGRAM_RADAR_COOLDOWN_HOURS ?? DEFAULT_COOLDOWN_HOURS);
    const since = new Date(Date.now() - hours * 3_600_000);
    const post = await this.prisma.telegramPost.findFirst({
      where: {
        productId,
        chatId,
        status: 'sent',
        sentAt: { gte: since },
      },
    });
    return Boolean(post);
  }

  private async logTelegramPost(
    candidate: RadarCandidate,
    chatId: string,
    status: 'sent' | 'skipped',
    reason?: string,
  ) {
    await this.prisma.telegramPost.create({
      data: {
        productId: candidate.offer.productId,
        offerId: candidate.offer.id,
        chatId,
        messageHash: candidate.messageHash,
        priceSnapshot: candidate.currentPrice,
        score: candidate.score,
        status,
        reason,
        payload: JSON.stringify(this.preview(candidate)),
      },
    }).catch((err) => {
      this.logger.warn(`Telegram post log ignorado: ${(err as Error).message}`);
    });
  }

  private preview(candidate: RadarCandidate) {
    return {
      productId: candidate.offer.productId,
      offerId: candidate.offer.id,
      product: candidate.offer.product.canonicalName ?? candidate.offer.product.title,
      marketplace: candidate.offer.marketplace?.name ?? null,
      price: candidate.currentPrice,
      pricePerUnit: candidate.offer.pricePerUnit ? Number(candidate.offer.pricePerUnit) : null,
      score: candidate.score,
      reasons: candidate.reasons,
      message: candidate.message,
    };
  }

  private async sendTelegram(chatId: string, text: string): Promise<void> {
    const token = process.env.TELEGRAM_BOT_TOKEN;
    if (!token) return;

    const response = await fetch(`https://api.telegram.org/bot${token}/sendMessage`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        chat_id: chatId,
        text,
        disable_web_page_preview: false,
      }),
    });

    if (!response.ok) {
      const body = await response.text().catch(() => '');
      throw new Error(`Telegram retornou ${response.status}: ${body}`);
    }
  }

  private priceOf(offer: { currentPrice?: unknown; price?: unknown }): number | null {
    const price = Number(offer.currentPrice ?? offer.price);
    return Number.isFinite(price) && price > 0 ? price : null;
  }

  private isPoupiBabyProduct(product: { title?: string | null; canonicalName?: string | null; category?: string | null }) {
    const text = this.normalize(`${product.canonicalName ?? product.title ?? ''} ${product.category ?? ''}`);
    return /fralda|pants|roupinha|pampers|huggies|mamypoko|babysec|lenco|toalhinha|umedecido|formula|aptamil|nan|ninho|nestogeno|milnutri|leite infantil|pomada|assadura|mamadeira|chupeta/.test(text);
  }

  private normalize(text: string): string {
    return text
      .toLowerCase()
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .replace(/[^a-z0-9]+/g, ' ')
      .trim();
  }

  private hash(value: string): string {
    return createHash('sha256').update(value).digest('hex');
  }

  private safeJson(value: string) {
    try {
      return JSON.parse(value);
    } catch {
      return {};
    }
  }
}
