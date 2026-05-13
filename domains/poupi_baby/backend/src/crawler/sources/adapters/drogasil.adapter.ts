import { Injectable } from '@nestjs/common';
import { VtexPharmacyAdapter } from './vtex-pharmacy.adapter';
import { BrowserSessionService } from '../browser-session.service';

@Injectable()
export class DrogasilSourceAdapter extends VtexPharmacyAdapter {
  constructor(browserSession: BrowserSessionService) {
    super('drogasil', ['drogasil.com.br'], browserSession);
  }
}
