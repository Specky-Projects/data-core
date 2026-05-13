import { ProductMatchingService } from './product-matching.service';
import { ProductNormalizerService } from './product-normalizer.service';

describe('ProductMatchingService', () => {
  const service = new ProductMatchingService(new ProductNormalizerService());

  it('returns high confidence for same formula with matching brand and weight', () => {
    const result = service.compare(
      { title: 'Formula Infantil Aptamil Premium 2 800g', brand: 'Aptamil' },
      { title: 'Aptamil Premium 2 Fórmula Infantil Lata 800 g' },
    );

    expect(result.verdict).toBe('match');
    expect(result.confidence).toBeGreaterThanOrEqual(82);
    expect(result.left.weight?.value).toBe(800);
  });

  it('penalizes conflicting package sizes', () => {
    const result = service.compare(
      { title: 'Fralda Pampers Confort Sec G 80 unidades' },
      { title: 'Fralda Pampers Confort Sec G 40 unidades' },
    );

    expect(result.confidence).toBeLessThan(82);
    expect(result.reasons).toContain('brand_match');
    expect(result.reasons).toContain('count_missing_or_conflict');
  });

  it('extracts volume and keeps possible matches when metadata is partial', () => {
    const result = service.compare(
      { title: 'Lenco Umedecido Huggies Supreme Care 48 Un' },
      { title: 'Lenços Umedecidos Huggies Supreme Care com 48 unidades' },
    );

    expect(result.verdict).toBe('match');
    expect(result.left.count?.value).toBe(48);
  });
});
