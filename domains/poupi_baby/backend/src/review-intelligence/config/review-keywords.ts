/**
 * Dicionário de keywords semânticas para análise de reviews.
 *
 * DESIGN DECISIONS:
 * - Configurável: adicionar categoria = só adicionar aqui. Zero código extra.
 * - Ponderado: weight 1-3 (1=fraco, 2=médio, 3=forte sinal)
 * - Variantes: termos alternativos do mesmo conceito
 * - Extensível: novos domínios de produto podem adicionar categorias específicas
 *
 * Para adicionar uma categoria:
 *   1. Adicionar ao tipo KeywordCategory
 *   2. Adicionar entrada no REVIEW_KEYWORDS
 *   3. Zero outras mudanças necessárias
 */

export type KeywordCategory =
  | 'durability'
  | 'comfort'
  | 'value_for_money'
  | 'quality'
  | 'shipping'
  | 'customer_service'
  | 'sizing'
  | 'safety'
  | 'performance'
  | 'aesthetics';

export type KeywordWeight = 1 | 2 | 3;

export interface KeywordEntry {
  term:      string;
  weight:    KeywordWeight;
  variants?: string[];
}

export interface KeywordConfig {
  positive: KeywordEntry[];
  negative: KeywordEntry[];
}

export const REVIEW_KEYWORDS: Record<KeywordCategory, KeywordConfig> = {

  durability: {
    positive: [
      { term: 'durável',     weight: 3, variants: ['resistente', 'sólido', 'robusto', 'resistiu'] },
      { term: 'durou',       weight: 3, variants: ['durou anos', 'durou meses', 'aguentou'] },
      { term: 'bem feito',   weight: 2, variants: ['construção boa', 'qualidade de construção'] },
    ],
    negative: [
      { term: 'quebrou',     weight: 3, variants: ['partiu', 'rachou', 'trincou', 'estragou'] },
      { term: 'frágil',      weight: 3, variants: ['fraco', 'delicado demais', 'mole'] },
      { term: 'durou pouco', weight: 3, variants: ['parou de funcionar', 'vida curta', 'descartável'] },
      { term: 'oxidou',      weight: 2, variants: ['enferrujou', 'descascou', 'manchou'] },
    ],
  },

  comfort: {
    positive: [
      { term: 'confortável', weight: 3, variants: ['conforto', 'gostoso', 'macio', 'suave'] },
      { term: 'leve',        weight: 2, variants: ['levinho', 'não pesa', 'fácil de usar'] },
      { term: 'ergonômico',  weight: 2, variants: ['bem projetado', 'intuitivo', 'prático'] },
    ],
    negative: [
      { term: 'incômodo',    weight: 3, variants: ['desconfortável', 'machuca', 'dói', 'cansa'] },
      { term: 'pesado',      weight: 2, variants: ['muito pesado', 'volumoso', 'grande demais'] },
    ],
  },

  value_for_money: {
    positive: [
      { term: 'vale a pena',    weight: 3, variants: ['valeu o preço', 'bom custo-benefício', 'vale cada centavo'] },
      { term: 'recomendo',      weight: 3, variants: ['recomendo muito', 'indicaria', 'compraria de novo'] },
      { term: 'custo-benefício', weight: 3, variants: ['melhor custo beneficio', 'boa relação qualidade preço'] },
      { term: 'barato',         weight: 2, variants: ['preço justo', 'acessível', 'em conta'] },
    ],
    negative: [
      { term: 'caro demais',   weight: 3, variants: ['overpriced', 'não vale o preço', 'cobram mais que vale'] },
      { term: 'enganoso',      weight: 3, variants: ['enganador', 'propaganda enganosa', 'diferente do anúncio'] },
      { term: 'joguei fora',   weight: 3, variants: ['perdi dinheiro', 'não valeu', 'desperdício'] },
    ],
  },

  quality: {
    positive: [
      { term: 'excelente',  weight: 3, variants: ['ótimo', 'perfeito', 'incrível', 'excepcional'] },
      { term: 'original',   weight: 2, variants: ['autêntico', 'genuíno', 'produto original'] },
      { term: 'acabamento', weight: 2, variants: ['acabamento bom', 'bem acabado', 'sem rebarbas'] },
    ],
    negative: [
      { term: 'defeituoso',  weight: 3, variants: ['com defeito', 'veio quebrado', 'parou de funcionar logo'] },
      { term: 'falsificado', weight: 3, variants: ['fake', 'cópia', 'pirata', 'não é original'] },
      { term: 'baixa qualidade', weight: 3, variants: ['qualidade ruim', 'barato por dentro', 'aparenta mais'] },
    ],
  },

  shipping: {
    positive: [
      { term: 'rápido',      weight: 2, variants: ['chegou rápido', 'entregou antes', 'pontual', 'prazo'] },
      { term: 'bem embalado', weight: 2, variants: ['embalagem boa', 'protegido', 'sem danos'] },
    ],
    negative: [
      { term: 'atrasou',    weight: 2, variants: ['demorou', 'não chegou', 'sumiu', 'perdido'] },
      { term: 'danificado', weight: 3, variants: ['amassado', 'quebrado na entrega', 'avariado', 'machucado'] },
    ],
  },

  customer_service: {
    positive: [
      { term: 'atendimento ótimo', weight: 2, variants: ['suporte excelente', 'resolveu rápido', 'prestativo'] },
      { term: 'trocaram',         weight: 2, variants: ['fizeram a troca', 'reembolsaram', 'devolveram'] },
    ],
    negative: [
      { term: 'não resolveu',   weight: 2, variants: ['ignoraram', 'sumiu', 'não atendeu', 'difícil de contatar'] },
      { term: 'sem suporte',    weight: 2, variants: ['abandonaram', 'pós-venda ruim', 'não tem assistência'] },
    ],
  },

  sizing: {
    positive: [
      { term: 'tamanho certo', weight: 2, variants: ['tamanho exato', 'como descrito', 'perfeito de tamanho'] },
    ],
    negative: [
      { term: 'muito pequeno', weight: 2, variants: ['menor que esperado', 'veste menor', 'ficou pequeno'] },
      { term: 'muito grande',  weight: 2, variants: ['maior que esperado', 'veste grande', 'gigante'] },
    ],
  },

  safety: {
    positive: [
      { term: 'seguro',      weight: 3, variants: ['certificado', 'aprovado', 'testado', 'sem riscos'] },
      { term: 'atóxico',     weight: 2, variants: ['não tóxico', 'seguro para crianças', 'inofensivo'] },
    ],
    negative: [
      { term: 'perigoso',    weight: 3, variants: ['risco de acidente', 'inseguro', 'cuidado'] },
      { term: 'queimou',     weight: 3, variants: ['pegou fogo', 'superaqueceu', 'explodiu', 'faiscou'] },
      { term: 'vazou',       weight: 3, variants: ['vaza', 'derramou', 'abriu', 'não vedou'] },
      { term: 'recall',      weight: 3 },
    ],
  },

  performance: {
    positive: [
      { term: 'rápido',      weight: 2, variants: ['ágil', 'fluido', 'sem travar', 'veloz'] },
      { term: 'potente',     weight: 2, variants: ['poderoso', 'forte', 'eficiente', 'funciona bem'] },
      { term: 'preciso',     weight: 2, variants: ['exato', 'calibrado', 'funciona como esperado'] },
    ],
    negative: [
      { term: 'trava',       weight: 3, variants: ['trava muito', 'lento', 'congela', 'demora'] },
      { term: 'fraco',       weight: 2, variants: ['não tem força', 'sem potência', 'ineficiente'] },
    ],
  },

  aesthetics: {
    positive: [
      { term: 'bonito',      weight: 2, variants: ['lindo', 'elegante', 'design bacana', 'esteticamente agradável'] },
      { term: 'como foto',   weight: 2, variants: ['igual às fotos', 'idêntico ao anúncio', 'como anunciado'] },
    ],
    negative: [
      { term: 'feio',        weight: 2, variants: ['horrível', 'design ruim', 'brega'] },
      { term: 'diferente',   weight: 2, variants: ['diferente da foto', 'não é como parece', 'color errada'] },
    ],
  },
};

// ── Utilitários ───────────────────────────────────────────────────────────────

export interface KeywordSignal {
  positiveScore: number;
  negativeScore: number;
  matches:       string[];
}

/**
 * Extrai sinais semânticos de um texto de review.
 * Normaliza acentos e case para maximizar cobertura.
 */
export function extractKeywordSignals(
  text: string,
): Record<KeywordCategory, KeywordSignal> {
  const normalized = text
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '');

  const result = {} as Record<KeywordCategory, KeywordSignal>;

  for (const [category, config] of Object.entries(REVIEW_KEYWORDS) as [KeywordCategory, KeywordConfig][]) {
    let positiveScore = 0;
    let negativeScore = 0;
    const matches: string[] = [];

    for (const kw of config.positive) {
      const terms = [kw.term, ...(kw.variants ?? [])].map((t) =>
        t.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, ''),
      );
      if (terms.some((t) => normalized.includes(t))) {
        positiveScore += kw.weight;
        matches.push(`+${kw.term}`);
      }
    }

    for (const kw of config.negative) {
      const terms = [kw.term, ...(kw.variants ?? [])].map((t) =>
        t.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, ''),
      );
      if (terms.some((t) => normalized.includes(t))) {
        negativeScore += kw.weight;
        matches.push(`-${kw.term}`);
      }
    }

    result[category] = { positiveScore, negativeScore, matches };
  }

  return result;
}

/**
 * Resume os top N sinais positivos e negativos de um conjunto de textos.
 */
export function aggregateKeywordSignals(
  signals: Record<KeywordCategory, KeywordSignal>[],
): {
  topPositive: Array<{ keyword: string; count: number; category: KeywordCategory }>;
  topNegative: Array<{ keyword: string; count: number; category: KeywordCategory }>;
} {
  const posMap = new Map<string, { count: number; category: KeywordCategory }>();
  const negMap = new Map<string, { count: number; category: KeywordCategory }>();

  for (const signal of signals) {
    for (const [category, data] of Object.entries(signal) as [KeywordCategory, KeywordSignal][]) {
      for (const match of data.matches) {
        const isPositive = match.startsWith('+');
        const keyword    = match.slice(1);
        const map        = isPositive ? posMap : negMap;

        const existing = map.get(keyword);
        if (existing) existing.count++;
        else map.set(keyword, { count: 1, category });
      }
    }
  }

  const toArray = (map: Map<string, { count: number; category: KeywordCategory }>) =>
    [...map.entries()]
      .map(([keyword, { count, category }]) => ({ keyword, count, category }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 10);

  return {
    topPositive: toArray(posMap),
    topNegative: toArray(negMap),
  };
}
