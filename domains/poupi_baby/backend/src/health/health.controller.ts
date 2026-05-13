import { Controller, Get } from '@nestjs/common';
import { HealthService } from './health.service';

@Controller('healthz')
export class HealthController {
  constructor(private readonly health: HealthService) {}

  @Get()
  getHealth() {
    return this.health.getHealth();
  }
}
