import { Global, Module } from '@nestjs/common';
import { EventEmitterModule } from '@nestjs/event-emitter';
import { EventBusService } from './event-bus.service';

/**
 * EventsModule — global, disponível em toda a aplicação.
 * Configura o EventEmitter2 com wildcard habilitado para facilitar
 * listeners como 'offer.*' ou 'ai-ops.*'.
 */
@Global()
@Module({
  imports: [
    EventEmitterModule.forRoot({
      wildcard:    true,    // permite listeners 'offer.*'
      delimiter:   '.',
      newListener: false,
      maxListeners: 30,
      verboseMemoryLeak: true,
    }),
  ],
  providers: [EventBusService],
  exports:   [EventBusService],
})
export class EventsModule {}
