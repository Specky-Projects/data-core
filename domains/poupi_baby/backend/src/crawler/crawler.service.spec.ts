import { Test, TestingModule } from '@nestjs/testing';
import { CrawlerService } from './crawler.service';
import { PrismaService } from '../prisma/prisma.service';
import { CacheService } from '../cache/cache.service';
import { EventBusService } from '../shared/events/event-bus.service';
import { ScraperHealthService } from './scraper-health.service';
import { SourceAdapterRegistry } from './sources/source-adapter.registry';
import { HtmlSnapshotService } from './sources/html-snapshot.service';
import { ScraperCircuitBreakerService } from './sources/circuit-breaker.service';
import { ProxyPoolService } from './sources/proxy-pool.service';
import { ScraperDomainMetricsService } from './sources/domain-metrics.service';

describe('CrawlerService', () => {
  let service: CrawlerService;

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        CrawlerService,
        { provide: PrismaService, useValue: {} },
        { provide: CacheService, useValue: {} },
        { provide: EventBusService, useValue: {} },
        { provide: ScraperHealthService, useValue: {} },
        { provide: SourceAdapterRegistry, useValue: { find: jest.fn() } },
        { provide: HtmlSnapshotService, useValue: { saveFailure: jest.fn() } },
        {
          provide: ScraperCircuitBreakerService,
          useValue: {
            canRequest: jest.fn(() => true),
            recordSuccess: jest.fn(),
            recordFailure: jest.fn(),
          },
        },
        {
          provide: ProxyPoolService,
          useValue: {
            next: jest.fn(),
            hasAlternative: jest.fn(() => false),
            recordSuccess: jest.fn(),
            recordFailure: jest.fn(),
          },
        },
        {
          provide: ScraperDomainMetricsService,
          useValue: {
            delayFor: jest.fn(() => ({ minMs: 3_000, maxMs: 12_000 })),
            record: jest.fn(),
          },
        },
      ],
    }).compile();

    service = module.get<CrawlerService>(CrawlerService);
  });

  it('should be defined', () => {
    expect(service).toBeDefined();
  });
});
