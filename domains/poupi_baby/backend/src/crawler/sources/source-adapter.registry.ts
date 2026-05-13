import { Injectable } from '@nestjs/common';
import { DrogasilSourceAdapter } from './adapters/drogasil.adapter';
import { DrogaRaiaSourceAdapter } from './adapters/droga-raia.adapter';
import { SourceAdapter } from './source-adapter.interface';

@Injectable()
export class SourceAdapterRegistry {
  private readonly adapters: SourceAdapter[];

  constructor(
    drogasil: DrogasilSourceAdapter,
    drogaRaia: DrogaRaiaSourceAdapter,
  ) {
    this.adapters = [drogasil, drogaRaia];
  }

  find(url: string, marketplace?: string): SourceAdapter | null {
    return this.adapters.find((adapter) => adapter.supports(url, marketplace)) ?? null;
  }

  list(): SourceAdapter[] {
    return this.adapters;
  }
}
