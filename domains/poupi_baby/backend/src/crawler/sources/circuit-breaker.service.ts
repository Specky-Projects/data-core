import { Injectable, Logger } from '@nestjs/common';

type CircuitState = {
  failures: number;
  openedUntil: number | null;
  halfOpen: boolean;
};

const FAILURE_THRESHOLD = 3;
const OPEN_MS = 30 * 60_000;

@Injectable()
export class ScraperCircuitBreakerService {
  private readonly logger = new Logger(ScraperCircuitBreakerService.name);
  private readonly states = new Map<string, CircuitState>();

  canRequest(source: string): boolean {
    const state = this.states.get(source);
    if (state?.halfOpen) return false;
    if (!state?.openedUntil) return true;

    if (Date.now() >= state.openedUntil) {
      this.logger.log(`[circuit] ${source} em half-open apos cooldown.`);
      state.openedUntil = null;
      state.halfOpen = true;
      return true;
    }

    return false;
  }

  recordSuccess(source: string): void {
    this.states.set(source, { failures: 0, openedUntil: null, halfOpen: false });
  }

  recordFailure(source: string): void {
    const current = this.states.get(source) ?? { failures: 0, openedUntil: null, halfOpen: false };
    const failures = current.failures + 1;
    const shouldOpen = current.halfOpen || failures >= FAILURE_THRESHOLD;
    const openMs = OPEN_MS * Math.min(4, Math.max(1, failures - FAILURE_THRESHOLD + 1));
    const openedUntil = shouldOpen ? Date.now() + openMs : current.openedUntil;

    if (!current.openedUntil && openedUntil) {
      this.logger.warn(`[circuit] ${source} aberto por ${openMs / 1000}s apos ${failures} falhas.`);
    }

    this.states.set(source, { failures, openedUntil, halfOpen: false });
  }

  getState(source: string) {
    const state = this.states.get(source) ?? { failures: 0, openedUntil: null, halfOpen: false };
    return {
      source,
      failures: state.failures,
      open: !!state.openedUntil && Date.now() < state.openedUntil,
      halfOpen: state.halfOpen,
      openedUntil: state.openedUntil ? new Date(state.openedUntil) : null,
    };
  }

  forceOpen(source: string, minutes = 30): void {
    this.states.set(source, {
      failures: FAILURE_THRESHOLD,
      openedUntil: Date.now() + minutes * 60_000,
      halfOpen: false,
    });
    this.logger.warn(`[circuit] ${source} aberto manualmente por ${minutes}min.`);
  }

  close(source: string): void {
    this.states.set(source, { failures: 0, openedUntil: null, halfOpen: false });
    this.logger.log(`[circuit] ${source} fechado manualmente.`);
  }
}
