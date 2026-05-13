export type CanonicalProduct = {
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

export function toSlug(text: string): string {
  return text
    .toLowerCase()
    .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '')
    .slice(0, 200);
}

export function normalizeText(text: string): string {
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

export function canonicalizeProduct(name: string): CanonicalProduct {
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
