import { Injectable, Logger } from '@nestjs/common';
import { EventEmitter2 } from '@nestjs/event-emitter';
import { DomainEvent, DomainEventType } from './domain-events';

/**
 * EventBus — barramento de eventos de domínio interno.
 *
 * Usa EventEmitter2 (in-process) hoje.
 * Caminho de evolução: substituir por Redis Streams quando volume justificar.
 *
 * Regras de uso:
 * - emit(): fire-and-forget, não aguarda handlers
 * - Handlers devem ser idempotentes e não lançar exceções
 * - Eventos são para comunicação cross-módulo, nunca para lógica crítica inline
 */
@Injectable()
export class EventBusService {
  private readonly logger = new Logger(EventBusService.name);

  constructor(private readonly emitter: EventEmitter2) {}

  /**
   * Publica um evento de domínio.
   * Todos os handlers registrados via @OnEvent() serão chamados assincronamente.
   */
  emit<T>(type: DomainEventType, payload: T): void {
    const event: DomainEvent<T> = {
      type,
      payload,
      timestamp: new Date(),
      traceId:   this.genTraceId(),
    };

    this.logger.debug(`[event] ${type} (traceId: ${event.traceId})`);
    this.emitter.emit(type, event);
  }

  /**
   * Registra um handler para um tipo de evento.
   * Prefira @OnEvent() nos módulos — este método é para casos dinâmicos.
   */
  on<T>(type: DomainEventType, handler: (event: DomainEvent<T>) => void | Promise<void>): void {
    this.emitter.on(type, (event: DomainEvent<T>) => {
      Promise.resolve(handler(event)).catch((err) => {
        this.logger.error(`[event] Handler de ${type} lançou exceção: ${err.message}`, err.stack);
      });
    });
  }

  private genTraceId(): string {
    return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`;
  }
}
