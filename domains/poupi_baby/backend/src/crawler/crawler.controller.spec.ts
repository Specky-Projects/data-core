import { Test, TestingModule } from '@nestjs/testing';
import { CrawlerController } from './crawler.controller';
import { CrawlerService } from './crawler.service';
import { CrawlerScheduler } from './crawler.scheduler';
import { ScraperHealthService } from './scraper-health.service';
import { ScraperQueueService } from './queue/scraper-queue.service';

describe('CrawlerController', () => {
  let controller: CrawlerController;

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      controllers: [CrawlerController],
      providers: [
        { provide: CrawlerService, useValue: {} },
        { provide: CrawlerScheduler, useValue: {} },
        { provide: ScraperHealthService, useValue: {} },
        { provide: ScraperQueueService, useValue: {} },
      ],
    }).compile();

    controller = module.get<CrawlerController>(CrawlerController);
  });

  it('should be defined', () => {
    expect(controller).toBeDefined();
  });
});
