import { Injectable } from '@nestjs/common';
import {
  ProductMatchInput,
  ProductMatchSignals,
  ProductMeasure,
  ProductMeasureKind,
} from './product-matching.types';

const STOPWORDS = new Set([
  'de',
  'da',
  'do',
  'das',
  'dos',
  'com',
  'sem',
  'para',
  'por',
  'em',
  'e',
  'o',
  'a',
  'os',
  'as',
  'kit',
  'combo',
  'lata',
  'pacote',
  'embalagem',
  'produto',
  'infantil',
  'bebe',
  'baby',
  'un',
  'und',
  'unid',
  'unidade',
  'unidades',
  'g',
  'gr',
  'gramas',
  'kg',
  'ml',
  'l',
  'lt',
]);

const KNOWN_BRANDS = [
  'aptamil',
  'nan',
  'nestle',
  'ninho',
  'enfamil',
  'milnutri',
  'danone',
  'pampers',
  'huggies',
  'mamypoko',
  'personal',
  'cremer',
  'johnson',
  'granado',
  'mustela',
];

@Injectable()
export class ProductNormalizerService {
  normalizeText(text: string): string {
    return text
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, ' ')
      .replace(/\s+/g, ' ')
      .trim();
  }

  tokenize(text: string): string[] {
    const normalized = this.normalizeText(text);
    return normalized
      .split(' ')
      .map((token) => this.canonicalToken(token))
      .filter((token) => token.length > 1 && !STOPWORDS.has(token) && !/^\d+(?:[,.]\d+)?$/.test(token));
  }

  signals(input: ProductMatchInput): ProductMatchSignals {
    const normalizedTitle = this.normalizeText(input.title);
    const explicitBrand = input.brand ? this.normalizeText(input.brand) : null;
    const inferredBrand = this.inferBrand(normalizedTitle);

    return {
      normalizedTitle,
      tokens: this.tokenize(input.title),
      brand: explicitBrand || inferredBrand,
      weight: this.extractMeasure(normalizedTitle, 'weight'),
      volume: this.extractMeasure(normalizedTitle, 'volume'),
      count: this.extractMeasure(normalizedTitle, 'count'),
    };
  }

  private inferBrand(normalizedTitle: string): string | null {
    const padded = ` ${normalizedTitle} `;
    return KNOWN_BRANDS.find((brand) => padded.includes(` ${brand} `)) ?? null;
  }

  private canonicalToken(token: string): string {
    const measure = token.match(/^(\d+(?:[,.]\d+)?)(kg|g|gr|ml|l|lt)$/);
    if (measure) return measure[2];

    const pluralMap: Record<string, string> = {
      lencos: 'lenco',
      lenços: 'lenco',
      umedecidos: 'umedecido',
      formulas: 'formula',
      fraldas: 'fralda',
      unidades: 'unidade',
    };

    return pluralMap[token] ?? token;
  }

  private extractMeasure(text: string, kind: ProductMeasureKind): ProductMeasure | null {
    if (kind === 'weight') {
      return this.firstMeasure(text, /(\d+(?:[,.]\d+)?)\s*(kg|quilo|quilos|g|gr|gramas)\b/g, kind);
    }

    if (kind === 'volume') {
      return this.firstMeasure(text, /(\d+(?:[,.]\d+)?)\s*(l|lt|litro|litros|ml|mililitros)\b/g, kind);
    }

    return this.firstMeasure(text, /(?:com\s*)?(\d+)\s*(un|und|unid|unidades|fraldas|lencos|lenços)\b/g, kind);
  }

  private firstMeasure(
    text: string,
    pattern: RegExp,
    kind: ProductMeasureKind,
  ): ProductMeasure | null {
    const match = pattern.exec(text);
    if (!match) return null;

    const rawValue = Number(match[1].replace(',', '.'));
    const rawUnit = match[2];

    if (!Number.isFinite(rawValue) || rawValue <= 0) return null;

    if (kind === 'weight') {
      const value = ['kg', 'quilo', 'quilos'].includes(rawUnit) ? rawValue * 1000 : rawValue;
      return { kind, value, unit: 'g', raw: match[0] };
    }

    if (kind === 'volume') {
      const value = ['l', 'lt', 'litro', 'litros'].includes(rawUnit) ? rawValue * 1000 : rawValue;
      return { kind, value, unit: 'ml', raw: match[0] };
    }

    return { kind, value: rawValue, unit: 'un', raw: match[0] };
  }
}
