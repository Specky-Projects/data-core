export type ProductMeasureKind = 'weight' | 'volume' | 'count';

export interface ProductMeasure {
  kind: ProductMeasureKind;
  value: number;
  unit: 'g' | 'ml' | 'un';
  raw: string;
}

export interface ProductMatchInput {
  title: string;
  brand?: string | null;
}

export interface ProductMatchSignals {
  normalizedTitle: string;
  tokens: string[];
  brand: string | null;
  weight: ProductMeasure | null;
  volume: ProductMeasure | null;
  count: ProductMeasure | null;
}

export interface ProductMatchResult {
  confidence: number;
  verdict: 'match' | 'possible_match' | 'no_match';
  reasons: string[];
  left: ProductMatchSignals;
  right: ProductMatchSignals;
  scores: {
    text: number;
    brand: number;
    weight: number;
    volume: number;
    count: number;
  };
}
