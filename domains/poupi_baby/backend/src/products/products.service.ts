import {
  BadRequestException,
  ForbiddenException,
  Injectable,
  NotFoundException,
  UnprocessableEntityException,
} from '@nestjs/common';

import { PrismaService } from '../prisma/prisma.service';
import { Prisma } from '@prisma/client';

import { CreateProductDto } from './dto/create-product.dto';
import { UpdateProductDto } from './dto/update-product.dto';
import { scrapeProduct } from '../crawler/scrapers/dispatcher';
import { detectMarketplace, supportedHosts } from '../crawler/scrapers/registry';
import { canonicalUrl, extractExternalId, normalizePrice } from '../crawler/url.utils';
import { getPlan, isAtLimit } from '../plans/plans.config';

function toSlug(text: string): string {
  return text
    .toLowerCase()
    .normalize('NFD').replace(/[̀-ͯ]/g, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '')
    .slice(0, 200);
}

/** Capitaliza o nome da loja vindo do registry (ex: 'magalu' → 'Magalu') */
function marketplaceName(entry: { name: string }): string {
  const MAP: Record<string, string> = {
    amazon: 'Amazon', mercadolivre: 'Mercado Livre', magalu: 'Magazine Luiza',
    kabum: 'Kabum', americanas: 'Americanas', shopee: 'Shopee',
    casasbahia: 'Casas Bahia', carrefour: 'Carrefour',
    drogasil: 'Drogasil', drogaraia: 'Droga Raia',
    paguemenos: 'Pague Menos', nissei: 'Farmacias Nissei',
    ultrafarma: 'Ultrafarma', drogariaspacheco: 'Drogarias Pacheco',
    drogariasaopaulo: 'Drogaria Sao Paulo', consultaremedios: 'Consulta Remedios',
    farma22: 'Farma22', panvel: 'Panvel',
  };
  return MAP[entry.name] ?? entry.name;
}

type RegionalInput = {
  city?: string | null;
  state?: string | null;
  neighborhood?: string | null;
};

type CanonicalProduct = {
  canonicalName: string;
  productFamilyName: string;
  productFamilySlug: string;
  variantLabel: string | null;
  measureValue: number | null;
  measureUnit: string | null;
  normalizedTitle: string;
  slug: string;
  brand: string | null;
  category: string | null;
  normalizedSize: string | null;
  quantity: number | null;
  unitType: string | null;
  keywords: string[];
};

const KNOWN_BRANDS = ['Pampers', 'Huggies', 'MamyPoko', 'Babysec', 'Ninho', 'Aptamil', 'Nestle', 'Nan', 'Milnutri'];

function normalizeText(text: string): string {
  return text
    .toLowerCase()
    .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9]+/g, ' ')
    .trim()
    .replace(/\s+/g, ' ');
}

function titleCase(text: string): string {
  return text
    .toLowerCase()
    .split(/\s+/)
    .filter(Boolean)
    .map((part) => part.length <= 3 ? part.toUpperCase() : part[0].toUpperCase() + part.slice(1))
    .join(' ');
}

function extractBrand(name: string): string | null {
  const normalized = normalizeText(name);
  return KNOWN_BRANDS.find((brand) => normalized.includes(normalizeText(brand))) ?? null;
}

function extractQuantity(name: string): { quantity: number | null; unitType: string | null; raw: string | null } {
  const units = name.match(/(\d{1,4})\s*(unidades|unidade|unds|und|un|fraldas|tiras|g|kg|ml|lata|latas)\b/i);
  if (!units) return { quantity: null, unitType: null, raw: null };

  const rawUnit = units[2].toLowerCase();
  const unitType = /kg/.test(rawUnit)
    ? 'g'
    : /^g$/.test(rawUnit)
    ? 'g'
    : /ml/.test(rawUnit)
      ? 'ml'
      : /lata/.test(rawUnit)
        ? 'lata'
        : 'unidade';

  const quantity = /kg/.test(rawUnit) ? Number(units[1]) * 1000 : Number(units[1]);
  return { quantity, unitType, raw: units[0] };
}

function extractSize(name: string, category: string | null): string | null {
  if (category !== 'Fraldas') return null;
  const normalized = normalizeText(name).toUpperCase();
  const match = normalized.match(/\b(RN|P|M|G|XG|XXG|XXXG|XXXXG|EG|XGG)\b/);
  return match?.[1] ?? null;
}

function inferCategory(name: string): string | null {
  const normalized = normalizeText(name);
  if (/fralda|pants|roupinha/.test(normalized)) return 'Fraldas';
  if (/formula|composto lacteo|leite|ninho|aptamil|nan|nestogeno|milnutri/.test(normalized)) return 'Formula infantil';
  if (/lenco|toalhinha|umedecido/.test(normalized)) return 'Lencos umedecidos';
  if (/pomada|assadura|hipoglos|bepantol|desitin/.test(normalized)) return 'Cuidados do bebe';
  if (/mamadeira|chupeta|bico|copo transicao|copo treinamento/.test(normalized)) return 'Alimentacao e acessorios';
  return null;
}

function validatePoupiBabyScope(name: string, category?: string | null): void {
  const normalized = normalizeText(`${name} ${category ?? ''}`);
  const allowedPatterns = [
    /\b(fralda|fraldas|pants|roupinha|pampers|huggies|mamypoko|mamy poko|babysec|personal baby)\b/,
    /\b(lenco|lencos|toalhinha|toalhinhas|umedecido|umedecidos)\b/,
    /\b(formula infantil|formula|aptamil|nan|ninho|nestogeno|enfamil|milnutri|composto lacteo|leite infantil)\b/,
    /\b(pomada|assadura|hipoglos|bepantol|desitin|creme preventivo)\b/,
    /\b(mamadeira|chupeta|bico|copo transicao|copo treinamento)\b/,
    /\b(mae e bebe|alimentacao infantil|higiene infantil|produtos infantis)\b/,
  ];
  const blockedPatterns = [
    /\b(cerveja|vinho|whisky|vodka|gin|cigarro|tabaco)\b/,
    /\b(anticoncepcional|preservativo|lubrificante)\b/,
    /\b(perfume|maquiagem|tintura|esmalte)\b/,
    /\b(suplemento adulto|termogenico|colageno|creatina|whey)\b/,
    /\b(dipirona|ibuprofeno|paracetamol|antibiotico|antigripal|pressao|diabetes)\b/,
  ];

  const isAllowed = allowedPatterns.some((pattern) => pattern.test(normalized));
  const isBlocked = blockedPatterns.some((pattern) => pattern.test(normalized));

  if (!isAllowed || isBlocked) {
    throw new UnprocessableEntityException(
      'Produto fora do escopo da Poupi Baby. No momento monitoramos fraldas, lencos umedecidos, formulas infantis e itens basicos de cuidado do bebe.',
    );
  }
}

function canonicalizeProduct(name: string): CanonicalProduct {
  const brand = extractBrand(name);
  const { quantity, unitType, raw: rawMeasure } = extractQuantity(name);
  const category = inferCategory(name);
  const normalizedSize = extractSize(name, category);

  let normalized = normalizeText(name);
  if (rawMeasure) {
    normalized = normalized.replace(normalizeText(rawMeasure), ' ');
  }

  normalized = normalized
    .replace(/\b\d{1,4}\s*(kg|g|gr|gramas|ml|l|lt|litros|lata|latas|unidades|unidade|unds|und|un|fraldas|tiras)\b/g, ' ')
    .replace(/\b\d+\s*pague\s*\d+\b/g, ' ')
    .replace(/\b(fr c|c|com|unidades|unidade|unds|und|un|fraldas|tiras)\b/g, ' ')
    .replace(/\b(rn|p|m|g|xg|xxg|xxxg|xxxxg|eg|xgg)\b/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();

  const keywords = Array.from(new Set(normalized.split(' ').filter((word) => word.length > 2)));
  const baseName = titleCase(normalized).replace(new RegExp(`^${brand ?? ''}\\s*`, 'i'), '').trim();
  const familyPieces = [brand, baseName].filter(Boolean) as string[];
  const productFamilyName = familyPieces.join(' ').replace(/\s+/g, ' ').trim() || name;
  const variantLabel = [
    normalizedSize,
    quantity && unitType ? `${quantity} ${unitType === 'unidade' ? 'unidades' : unitType}` : null,
  ].filter(Boolean).join(' - ') || null;
  const pieces = [
    brand,
    baseName,
    normalizedSize,
    quantity && unitType ? `${quantity} ${unitType === 'unidade' ? 'unidades' : unitType}` : null,
  ].filter(Boolean) as string[];

  const canonicalName = pieces.join(' ').replace(/\s+/g, ' ').trim() || name;
  const normalizedTitle = normalizeText(canonicalName);

  return {
    canonicalName,
    productFamilyName,
    productFamilySlug: toSlug(productFamilyName),
    variantLabel,
    measureValue: quantity,
    measureUnit: unitType,
    normalizedTitle,
    slug: toSlug(canonicalName),
    brand,
    category,
    normalizedSize,
    quantity,
    unitType,
    keywords,
  };
}

function pricePerUnit(price: number, quantity: number | null): number | null {
  if (!quantity || quantity <= 0) return null;
  return Math.round((price / quantity) * 10_000) / 10_000;
}

function normalizeRegion(input?: RegionalInput): RegionalInput {
  return {
    city: input?.city?.trim() || null,
    state: input?.state?.trim().toUpperCase().slice(0, 2) || null,
    neighborhood: input?.neighborhood?.trim() || null,
  };
}

// ---------------------------------------------------------------------------
// Service
// ---------------------------------------------------------------------------

@Injectable()
export class ProductsService {
  constructor(private prisma: PrismaService) {}

  // ── Adicionar por URL ────────────────────────────────────────────────────

  /**
   * Scraping → cria/atualiza produto + oferta → vincula ao usuário via Alert.
   * Evita duplicata: mesmo usuário + mesmo produto → 409.
   */
  async addByUrl(url: string, userId: string, regionInput?: RegionalInput) {
    // 0. Verifica quota do plano
    // 1. Valida host e normaliza URL (etapas 2.3 + 2.4)
    let parsed: URL;
    try { parsed = new URL(url); } catch { throw new BadRequestException('URL inválida'); }

    const entry = detectMarketplace(url);
    if (!entry) {
      throw new BadRequestException(`Marketplace não suportado: ${parsed.hostname}. Suportados: ${supportedHosts().join(', ')}`);
    }

    const cleanUrl = canonicalUrl(url);          // remove UTM, affiliate, etc.
    const hostname = parsed.hostname.replace(/^www\./, '');

    // 2. Scraping
    const result = await scrapeProduct(cleanUrl, entry.name);
    if (!result.success || !result.name) {
      throw new UnprocessableEntityException(result.error ?? 'Falha no scraping');
    }
    validatePoupiBabyScope(result.name, result.category);

    // Normaliza preço (etapa 2.2) — garante number limpo mesmo se scraper retornar string
    const scrapedPrice = normalizePrice(result.price);
    if (!scrapedPrice) {
      throw new UnprocessableEntityException('Preço inválido retornado pelo scraper');
    }

    const canonical = canonicalizeProduct(result.name);
    const mlName = marketplaceName(entry);
    const region = normalizeRegion(regionInput);

    // 3. Find-or-create marketplace
    let marketplace = await this.prisma.marketplace.findFirst({
      where: { baseUrl: `https://${hostname}` },
    });
    if (!marketplace) {
      marketplace = await this.prisma.marketplace.create({
        data: { name: mlName, baseUrl: `https://${hostname}` },
      });
    }

    // 4. Upsert produto global (por slug)
    const product = await this.prisma.product.upsert({
      where: { slug: canonical.slug },
      update: {
        title: canonical.canonicalName,
        canonicalName: canonical.canonicalName,
        productFamilyName: canonical.productFamilyName,
        productFamilySlug: canonical.productFamilySlug,
        variantLabel: canonical.variantLabel,
        measureValue: canonical.measureValue,
        measureUnit: canonical.measureUnit,
        normalizedTitle: canonical.normalizedTitle,
        brand: canonical.brand,
        category: canonical.category ?? result.category ?? null,
        ean: result.ean ?? null,
        normalizedSize: canonical.normalizedSize,
        quantity: canonical.quantity,
        unitType: canonical.unitType,
        keywords: JSON.stringify(canonical.keywords),
        imageUrl: result.imageUrl ?? undefined,
      },
      create: {
        title: canonical.canonicalName,
        canonicalName: canonical.canonicalName,
        productFamilyName: canonical.productFamilyName,
        productFamilySlug: canonical.productFamilySlug,
        variantLabel: canonical.variantLabel,
        measureValue: canonical.measureValue,
        measureUnit: canonical.measureUnit,
        normalizedTitle: canonical.normalizedTitle,
        slug: canonical.slug,
        brand: canonical.brand,
        category: canonical.category ?? result.category ?? null,
        ean: result.ean ?? null,
        normalizedSize: canonical.normalizedSize,
        quantity: canonical.quantity,
        unitType: canonical.unitType,
        keywords: JSON.stringify(canonical.keywords),
        imageUrl: result.imageUrl ?? null,
      },
    });

    // 5. Verifica duplicata: usuário já monitora este produto?
    const existing = await this.prisma.alert.findFirst({
      where: { userId, productId: product.id },
    });
    if (existing && !existing.active) {
      await this.prisma.alert.update({ where: { id: existing.id }, data: { active: true } });
    }
    if (!existing) {
      await this.enforceProductQuota(userId);
    }

    if (result.regionalOffers?.length) {
      const now = new Date();
      await Promise.all(result.regionalOffers.map(async (regionalOffer) => {
        const sellerMarketplace = await this.prisma.marketplace.upsert({
          where: { slug: regionalOffer.marketplaceSlug },
          update: {
            name: regionalOffer.marketplaceName,
            baseUrl: `https://consultaremedios.com.br/seller/${regionalOffer.marketplaceSlug}`,
            active: true,
          },
          create: {
            name: regionalOffer.marketplaceName,
            slug: regionalOffer.marketplaceSlug,
            baseUrl: `https://consultaremedios.com.br/seller/${regionalOffer.marketplaceSlug}`,
            active: true,
          },
        });

        await this.prisma.offer.upsert({
          where: {
            marketplaceId_externalId: {
              marketplaceId: sellerMarketplace.id,
              externalId: regionalOffer.externalId,
            },
          },
          update: {
            price: regionalOffer.currentPrice,
            currentPrice: regionalOffer.currentPrice,
            originalPrice: regionalOffer.originalPrice,
            pricePerUnit: pricePerUnit(regionalOffer.currentPrice, canonical.quantity),
            productUrl: regionalOffer.url,
            availability: regionalOffer.availability,
            stock: regionalOffer.stock,
            scrapingStatus: 'success',
            lastCheckedAt: now,
            lastScrapedAt: now,
            lastValidPrice: regionalOffer.currentPrice,
            lastValidScrapedAt: now,
            city: region.city,
            state: region.state,
            neighborhood: region.neighborhood,
          },
          create: {
            productId: product.id,
            marketplaceId: sellerMarketplace.id,
            externalId: regionalOffer.externalId,
            price: regionalOffer.currentPrice,
            currentPrice: regionalOffer.currentPrice,
            originalPrice: regionalOffer.originalPrice,
            pricePerUnit: pricePerUnit(regionalOffer.currentPrice, canonical.quantity),
            productUrl: regionalOffer.url,
            availability: regionalOffer.availability,
            stock: regionalOffer.stock,
            scrapingStatus: 'success',
            lastScrapedAt: now,
            lastValidPrice: regionalOffer.currentPrice,
            lastValidScrapedAt: now,
            city: region.city,
            state: region.state,
            neighborhood: region.neighborhood,
          },
        });
      }));

      if (!existing) {
        const targetPrice = Math.round(scrapedPrice * 0.9 * 100) / 100;
        await this.prisma.alert.create({
          data: { userId, productId: product.id, targetPrice },
        });
      }

      return this.prisma.product.findUnique({
        where: { id: product.id },
        include: { offers: { include: { marketplace: true } } },
      });
    }

    // 6. Upsert oferta — externalId real (etapa 2.4) + URL canônica (etapa 2.3)
    const externalId = extractExternalId(cleanUrl, entry.name);
    const unitPrice = pricePerUnit(scrapedPrice, canonical.quantity);
    const now = new Date();
    await this.prisma.offer.upsert({
      where: { marketplaceId_externalId: { marketplaceId: marketplace.id, externalId } },
      update: {
        price: scrapedPrice,
        currentPrice: scrapedPrice,
        originalPrice: result.originalPrice ?? null,
        pricePerUnit: unitPrice,
        productUrl: cleanUrl,
        availability: result.availability ?? true,
        scrapingStatus: 'success',
        lastCheckedAt: now,
        lastScrapedAt: now,
        lastValidPrice: scrapedPrice,
        lastValidScrapedAt: now,
        city: region.city,
        state: region.state,
        neighborhood: region.neighborhood,
      },
      create: {
        productId: product.id,
        marketplaceId: marketplace.id,
        externalId,
        price: scrapedPrice,
        currentPrice: scrapedPrice,
        originalPrice: result.originalPrice ?? null,
        pricePerUnit: unitPrice,
        productUrl: cleanUrl,
        availability: result.availability ?? true,
        scrapingStatus: 'success',
        lastScrapedAt: now,
        lastValidPrice: scrapedPrice,
        lastValidScrapedAt: now,
        city: region.city,
        state: region.state,
        neighborhood: region.neighborhood,
      },
    });

    // 7. Cria Alert como vínculo usuário-produto (targetPrice = preço atual × 0.9)
    if (!existing) {
      const targetPrice = Math.round(scrapedPrice * 0.9 * 100) / 100;
      await this.prisma.alert.create({
        data: { userId, productId: product.id, targetPrice },
      });
    }

    // 8. Retorna produto com ofertas
    return this.prisma.product.findUnique({
      where: { id: product.id },
      include: { offers: { include: { marketplace: true } } },
    });
  }

  // ── Listar produtos do usuário ───────────────────────────────────────────

  async findAllByUser(userId: string) {
    return this.prisma.product.findMany({
      where: {
        deletedAt: null,
        alerts: { some: { userId } },
      },
      include: { offers: { include: { marketplace: true } } },
      orderBy: { createdAt: 'desc' },
    });
  }

  // ── Remover produto do usuário ───────────────────────────────────────────

  /**
   * Remove o produto da watchlist do usuário:
   *   - Desativa todos os alerts do usuário para este produto
   *   - Se nenhum outro usuário monitora, faz soft-delete do produto
   */
  async removeFromUser(productId: string, userId: string) {
    const product = await this.prisma.product.findUnique({
      where: { id: productId, deletedAt: null },
    });
    if (!product) throw new NotFoundException(`Produto não encontrado: ${productId}`);

    // Desativa alerts do usuário para este produto
    await this.prisma.alert.updateMany({
      where: { userId, productId },
      data: { active: false },
    });

    // Soft-delete se nenhum outro usuário monitora
    const otherMonitors = await this.prisma.alert.count({
      where: { productId, active: true, userId: { not: userId } },
    });
    if (otherMonitors === 0) {
      await this.prisma.product.update({
        where: { id: productId },
        data: { deletedAt: new Date() },
      });
    }

    return { success: true };
  }

  // ── CRUD genérico (admin/interno) ────────────────────────────────────────

  async create(data: CreateProductDto) {
    return this.prisma.product.create({ data });
  }

  async findAll() {
    return this.prisma.product.findMany({
      where: { deletedAt: null },
      include: { offers: { include: { marketplace: true } } },
      orderBy: { createdAt: 'desc' },
    });
  }

  async findOne(id: string) {
    const product = await this.prisma.product.findUnique({
      where: { id, deletedAt: null },
      include: { offers: { include: { marketplace: true } } },
    });
    if (!product) throw new NotFoundException(`Produto não encontrado: ${id}`);
    if (!product.productFamilySlug) return product;

    const variants = await this.prisma.product.findMany({
      where: {
        deletedAt: null,
        productFamilySlug: product.productFamilySlug,
        id: { not: product.id },
      },
      include: { offers: { include: { marketplace: true } } },
      orderBy: [
        { measureValue: 'asc' },
        { createdAt: 'desc' },
      ],
      take: 12,
    });

    return { product, offers: product.offers, variants };
  }

  async update(id: string, data: UpdateProductDto) {
    try {
      return await this.prisma.product.update({ where: { id, deletedAt: null }, data });
    } catch (e) {
      if (e instanceof Prisma.PrismaClientKnownRequestError && e.code === 'P2025') {
        throw new NotFoundException(`Produto não encontrado: ${id}`);
      }
      throw e;
    }
  }

  async remove(id: string) {
    try {
      return await this.prisma.product.update({
        where: { id, deletedAt: null },
        data: { deletedAt: new Date() },
      });
    } catch (e) {
      if (e instanceof Prisma.PrismaClientKnownRequestError && e.code === 'P2025') {
        throw new NotFoundException(`Produto não encontrado: ${id}`);
      }
      throw e;
    }
  }

  // ── Quota enforcement ────────────────────────────────────────────────────

  /**
   * Verifica se o usuário atingiu o limite de produtos do seu plano.
   * Lança 403 com mensagem clara se o limite foi atingido.
   */
  private async enforceProductQuota(userId: string): Promise<void> {
    // Busca plano ativo do usuário (subscription mais recente ativa)
    const sub = await this.prisma.subscription.findFirst({
      where: { userId, status: 'active' },
      orderBy: { createdAt: 'desc' },
    });

    const planId = sub?.plan ?? 'free';
    const plan   = getPlan(planId);

    if (plan.maxProducts === -1) return; // ilimitado

    // Conta produtos ativos do usuário (via alerts)
    const count = await this.prisma.alert.count({
      where: { userId, active: true, product: { deletedAt: null } },
    });

    if (isAtLimit(count, plan.maxProducts)) {
      throw new ForbiddenException(
        `Limite do plano ${plan.name} atingido: ${plan.maxProducts} produto${plan.maxProducts !== 1 ? 's' : ''}. ` +
        `Faça upgrade para monitorar mais produtos.`,
      );
    }
  }

  /**
   * Retorna o resumo de quota do usuário (usado pelo frontend).
   */
  async getQuotaSummary(userId: string) {
    const sub = await this.prisma.subscription.findFirst({
      where: { userId, status: 'active' },
      orderBy: { createdAt: 'desc' },
    });

    const planId   = sub?.plan ?? 'free';
    const plan     = getPlan(planId);
    const current  = await this.prisma.alert.count({
      where: { userId, active: true, product: { deletedAt: null } },
    });

    return {
      plan:        plan.id,
      planName:    plan.name,
      current,
      max:         plan.maxProducts,
      unlimited:   plan.maxProducts === -1,
      atLimit:     isAtLimit(current, plan.maxProducts),
      features: {
        dealScore:         plan.dealScore,
        csvExport:         plan.csvExport,
        apiAccess:         plan.apiAccess,
        advancedAnalytics: plan.advancedAnalytics,
        historyDays:       plan.priceHistoryDays,
      },
    };
  }
}
