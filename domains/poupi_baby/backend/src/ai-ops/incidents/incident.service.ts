import { Injectable, Logger } from '@nestjs/common';
import { PrismaService } from '../../prisma/prisma.service';

export type IncidentSeverity = 'low' | 'medium' | 'high' | 'critical';
export type IncidentStatus   = 'open' | 'acknowledged' | 'resolved' | 'dismissed';

export interface CreateIncidentDto {
  marketplace?:  string;
  incidentType:  string;
  severity:      IncidentSeverity;
  inputData:     Record<string, unknown>;
  rootCause?:    string;
  suggestions?:  string[];
  confidence?:   number;
  aiProvider?:   string;
  aiModel?:      string;
  aiTokensUsed?: number;
}

@Injectable()
export class IncidentService {
  private readonly logger = new Logger(IncidentService.name);

  constructor(private readonly prisma: PrismaService) {}

  async create(dto: CreateIncidentDto) {
    const incident = await this.prisma.aiIncident.create({
      data: {
        marketplace:  dto.marketplace,
        incidentType: dto.incidentType,
        severity:     dto.severity,
        inputData:    JSON.stringify(dto.inputData),
        rootCause:    dto.rootCause,
        suggestions:  JSON.stringify(dto.suggestions ?? []),
        confidence:   dto.confidence,
        aiProvider:   dto.aiProvider,
        aiModel:      dto.aiModel,
        aiTokensUsed: dto.aiTokensUsed,
        status:       'open',
      },
    });

    this.logger.warn(
      `[incident] Novo incidente ${dto.severity.toUpperCase()} — ${dto.marketplace ?? 'sistema'} — ${dto.incidentType}`,
    );

    return incident;
  }

  /** Verifica se há incidente aberto recente (< 30min) para o marketplace */
  async findOpenIncident(marketplace: string): Promise<boolean> {
    const since = new Date(Date.now() - 30 * 60_000);
    const count = await this.prisma.aiIncident.count({
      where: {
        marketplace,
        status:     { in: ['open', 'acknowledged'] },
        detectedAt: { gte: since },
      },
    });
    return count > 0;
  }

  async resolve(id: string, note?: string) {
    return this.prisma.aiIncident.update({
      where: { id },
      data: {
        status:        'resolved',
        resolvedAt:    new Date(),
        resolutionNote: note,
      },
    });
  }

  async acknowledge(id: string) {
    return this.prisma.aiIncident.update({
      where: { id },
      data: { status: 'acknowledged' },
    });
  }

  async getOpen(limit = 20) {
    const incidents = await this.prisma.aiIncident.findMany({
      where:   { status: { in: ['open', 'acknowledged'] } },
      orderBy: [
        // critical primeiro, depois por tempo
        { detectedAt: 'desc' },
      ],
      take: limit,
    });

    return incidents.map((i) => ({
      ...i,
      inputData:   this.parseJson(i.inputData,   {}),
      suggestions: this.parseJson(i.suggestions, []),
    }));
  }

  async getRecent(limit = 50) {
    const incidents = await this.prisma.aiIncident.findMany({
      orderBy: { detectedAt: 'desc' },
      take:    limit,
    });

    return incidents.map((i) => ({
      ...i,
      inputData:   this.parseJson(i.inputData,   {}),
      suggestions: this.parseJson(i.suggestions, []),
    }));
  }

  private parseJson<T>(str: string, fallback: T): T {
    try { return JSON.parse(str); } catch { return fallback; }
  }
}
