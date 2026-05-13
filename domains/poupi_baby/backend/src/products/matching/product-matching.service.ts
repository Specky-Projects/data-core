import { Injectable } from '@nestjs/common';
import {
  ProductMatchInput,
  ProductMatchResult,
  ProductMeasure,
} from './product-matching.types';
import { ProductNormalizerService } from './product-normalizer.service';

@Injectable()
export class ProductMatchingService {
  constructor(private readonly normalizer: ProductNormalizerService) {}

  compare(left: ProductMatchInput, right: ProductMatchInput): ProductMatchResult {
    const leftSignals = this.normalizer.signals(left);
    const rightSignals = this.normalizer.signals(right);

    const text = this.textScore(leftSignals.tokens, rightSignals.tokens);
    const brand = this.brandScore(leftSignals.brand, rightSignals.brand);
    const weight = this.measureScore(leftSignals.weight, rightSignals.weight);
    const volume = this.measureScore(leftSignals.volume, rightSignals.volume);
    const count = this.measureScore(leftSignals.count, rightSignals.count);

    const scores = { text, brand, weight, volume, count };
    const rawConfidence = Math.round((
      text * 0.45 +
      brand * 0.25 +
      weight * 0.12 +
      volume * 0.10 +
      count * 0.08
    ) * 100);
    const confidence = this.applyConflictCaps(rawConfidence, {
      weight: this.hasConflict(leftSignals.weight, rightSignals.weight, weight),
      volume: this.hasConflict(leftSignals.volume, rightSignals.volume, volume),
      count: this.hasConflict(leftSignals.count, rightSignals.count, count),
    });

    return {
      confidence,
      verdict: confidence >= 82 ? 'match' : confidence >= 62 ? 'possible_match' : 'no_match',
      reasons: this.reasons(scores),
      left: leftSignals,
      right: rightSignals,
      scores,
    };
  }

  private textScore(left: string[], right: string[]): number {
    if (left.length === 0 || right.length === 0) return 0;

    const leftSet = new Set(left);
    const rightSet = new Set(right);
    const intersection = [...leftSet].filter((token) => rightSet.has(token)).length;
    const union = new Set([...leftSet, ...rightSet]).size;
    return intersection / union;
  }

  private brandScore(left: string | null, right: string | null): number {
    if (!left || !right) return 0.5;
    return left === right ? 1 : 0;
  }

  private measureScore(left: ProductMeasure | null, right: ProductMeasure | null): number {
    if (!left && !right) return 0.75;
    if (!left || !right) return 0.35;
    if (left.unit !== right.unit) return 0;

    const diff = Math.abs(left.value - right.value);
    const base = Math.max(left.value, right.value);
    const ratio = base === 0 ? 1 : diff / base;

    if (ratio <= 0.02) return 1;
    if (ratio <= 0.08) return 0.75;
    if (ratio <= 0.15) return 0.45;
    return 0;
  }

  private hasConflict(
    left: ProductMeasure | null,
    right: ProductMeasure | null,
    score: number,
  ): boolean {
    return !!left && !!right && score === 0;
  }

  private applyConflictCaps(
    confidence: number,
    conflicts: { weight: boolean; volume: boolean; count: boolean },
  ): number {
    if (conflicts.weight || conflicts.volume) return Math.min(confidence, 72);
    if (conflicts.count) return Math.min(confidence, 78);
    return confidence;
  }

  private reasons(scores: ProductMatchResult['scores']): string[] {
    const reasons: string[] = [];

    if (scores.text >= 0.7) reasons.push('text_strong');
    else if (scores.text >= 0.45) reasons.push('text_partial');
    else reasons.push('text_weak');

    if (scores.brand === 1) reasons.push('brand_match');
    else if (scores.brand === 0) reasons.push('brand_conflict');
    else reasons.push('brand_missing');

    if (scores.weight === 1) reasons.push('weight_match');
    else if (scores.weight <= 0.35) reasons.push('weight_missing_or_conflict');

    if (scores.volume === 1) reasons.push('volume_match');
    else if (scores.volume <= 0.35) reasons.push('volume_missing_or_conflict');

    if (scores.count === 1) reasons.push('count_match');
    else if (scores.count <= 0.35) reasons.push('count_missing_or_conflict');

    return reasons;
  }
}
