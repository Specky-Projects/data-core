/**
 * strategy.ts
 *
 * Utilitário para encadear múltiplas estratégias de extração.
 *
 * Uso:
 *   const product = await runStrategies([
 *     () => strategyNextData(url),
 *     () => strategyJsonLd(url),
 *     () => strategyCSS(url),
 *   ]);
 *
 * Cada estratégia retorna T (sucesso) ou null (tentar próxima).
 * Se todas retornarem null, runStrategies retorna null.
 */

export type Strategy<T> = () => Promise<T | null>;

/**
 * Executa estratégias em sequência, parando na primeira que retornar não-null.
 * Erros individuais são capturados e logados — nunca propagam para fora.
 *
 * @param strategies Array de funções que retornam Promise<T | null>
 * @param label      Identificador para log (ex: 'kabum')
 */
export async function runStrategies<T>(
  strategies: Strategy<T>[],
  label = 'scraper',
): Promise<T | null> {
  for (let i = 0; i < strategies.length; i++) {
    try {
      const result = await strategies[i]();
      if (result !== null && result !== undefined) {
        return result;
      }
    } catch (err) {
      console.warn(`[${label}] estratégia ${i + 1} falhou:`, (err as Error).message ?? err);
    }
  }
  return null;
}

// ---------------------------------------------------------------------------
// Helpers de extração compartilhados entre scrapers
// ---------------------------------------------------------------------------

/** Extrai JSON de <script id="__NEXT_DATA__"> */
export function parseNextData<T = unknown>(html: string): T | null {
  const match = html.match(/<script[^>]*id="__NEXT_DATA__"[^>]*>([\s\S]*?)<\/script>/);
  if (!match) return null;
  try { return JSON.parse(match[1]) as T; } catch { return null; }
}

/** Extrai todos os blocos JSON-LD do HTML */
export function parseJsonLd(html: string): Record<string, unknown>[] {
  const results: Record<string, unknown>[] = [];
  const regex = /<script[^>]*type="application\/ld\+json"[^>]*>([\s\S]*?)<\/script>/gi;
  let match: RegExpExecArray | null;
  while ((match = regex.exec(html)) !== null) {
    try {
      const parsed = JSON.parse(match[1]);
      if (typeof parsed === 'object' && parsed !== null) results.push(parsed as Record<string, unknown>);
    } catch { /* ignora bloco inválido */ }
  }
  return results;
}

/** Extrai bloco JSON-LD com @type = 'Product' */
export function findProductJsonLd(html: string): Record<string, unknown> | null {
  return parseJsonLd(html).find((b) => b['@type'] === 'Product') ?? null;
}

/** Extrai preço e nome de um bloco JSON-LD Product */
export function extractFromProductJsonLd(block: Record<string, unknown>): {
  price: number | null;
  originalPrice: number | null;
  name: string | null;
  imageUrl: string | null;
  availability: boolean;
} {
  const fallback = { price: null, originalPrice: null, name: null, imageUrl: null, availability: true };

  const offers = (block.offers ?? block.Offers) as Record<string, unknown> | undefined;
  if (!offers) return fallback;

  const price = parseFloat(String(offers.price ?? offers.lowPrice ?? '')) || null;
  const originalPrice = parseFloat(String(offers.highPrice ?? '')) || null;

  const name = typeof block.name === 'string' ? block.name : null;

  const imageUrl =
    typeof block.image === 'string'
      ? block.image
      : Array.isArray(block.image)
        ? String(block.image[0])
        : null;

  const avail = String(offers.availability ?? '').toLowerCase();
  const availability =
    !avail || avail.includes('instock') || avail.includes('inStore') || avail.includes('disponivel');

  return {
    price: price && price > 0 ? Math.round(price * 100) / 100 : null,
    originalPrice: originalPrice && originalPrice > (price ?? 0) ? Math.round(originalPrice * 100) / 100 : null,
    name,
    imageUrl,
    availability,
  };
}
