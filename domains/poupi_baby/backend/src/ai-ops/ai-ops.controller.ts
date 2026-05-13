import {
  Controller, Get, Param, Patch, Body, UseGuards, Query,
} from '@nestjs/common';
import { AuthGuard } from '@nestjs/passport';
import { AdminGuard } from '../common/admin.guard';
import { IncidentService } from './incidents/incident.service';

/**
 * AI Ops Controller — endpoints para o dashboard operacional.
 * Todos os endpoints requerem autenticação + role admin.
 */
@Controller('ai-ops')
@UseGuards(AuthGuard('jwt'), AdminGuard)
export class AiOpsController {
  constructor(private readonly incidents: IncidentService) {}

  /** Lista incidentes abertos (open + acknowledged) */
  @Get('incidents')
  getOpenIncidents() {
    return this.incidents.getOpen();
  }

  /** Histórico de incidentes recentes */
  @Get('incidents/history')
  getRecentIncidents(@Query('limit') limit?: string) {
    return this.incidents.getRecent(limit ? parseInt(limit, 10) : 50);
  }

  /** Marca incidente como acknowledged */
  @Patch('incidents/:id/acknowledge')
  acknowledge(@Param('id') id: string) {
    return this.incidents.acknowledge(id);
  }

  /** Marca incidente como resolvido com nota opcional */
  @Patch('incidents/:id/resolve')
  resolve(
    @Param('id') id: string,
    @Body('note') note?: string,
  ) {
    return this.incidents.resolve(id, note);
  }
}
