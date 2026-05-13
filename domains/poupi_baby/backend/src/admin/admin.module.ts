import { Module } from '@nestjs/common';
import { PrismaModule }    from '../prisma/prisma.module';
import { CrawlerModule }   from '../crawler/crawler.module';
import { AnalyticsModule } from '../analytics/analytics.module';
import { AiOpsModule }     from '../ai-ops/ai-ops.module';
import { PromotionsModule } from '../promotions/promotions.module';
import { AdminController } from './admin.controller';
import { AdminService } from './admin.service';

/**
 * AdminModule
 *
 * Expõe todos os endpoints de /admin/*.
 * Requer JWT válido + role === 'admin' (aplicado no controller via AdminGuard).
 *
 * Dependências:
 *   PrismaModule   → listagem/contagem de usuários, produtos, etc.
 *   CrawlerModule  → ScraperHealthService (ranking + timeline)
 *   AnalyticsModule → AnalyticsService (eventos, funil, séries temporais)
 *   AiOpsModule    → IncidentService (incidentes abertos/histórico)
 */
@Module({
  imports: [
    PrismaModule,
    CrawlerModule,
    AnalyticsModule,
    AiOpsModule,
    PromotionsModule,
  ],
  controllers: [AdminController],
  providers: [AdminService],
})
export class AdminModule {}
