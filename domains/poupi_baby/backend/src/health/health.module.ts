import { Module } from '@nestjs/common';
import { RedisCacheModule } from '../cache/cache.module';
import { CrawlerModule } from '../crawler/crawler.module';
import { PrismaModule } from '../prisma/prisma.module';
import { HealthController } from './health.controller';
import { HealthService } from './health.service';

@Module({
  imports: [PrismaModule, RedisCacheModule, CrawlerModule],
  controllers: [HealthController],
  providers: [HealthService],
})
export class HealthModule {}
