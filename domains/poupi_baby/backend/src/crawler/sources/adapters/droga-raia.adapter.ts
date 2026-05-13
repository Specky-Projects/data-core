import { Injectable } from '@nestjs/common';
import { VtexPharmacyAdapter } from './vtex-pharmacy.adapter';
import { BrowserSessionService } from '../browser-session.service';

@Injectable()
export class DrogaRaiaSourceAdapter extends VtexPharmacyAdapter {
  constructor(browserSession: BrowserSessionService) {
    super('drogaraia', ['drogaraia.com.br'], browserSession);
  }
}
