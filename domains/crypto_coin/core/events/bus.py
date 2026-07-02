"""
Event Bus — comunicação interna desacoplada.

Implementação síncrona/assíncrona in-process (monolito modular).
Não usa Kafka, Redis ou qualquer broker externo.

Uso:
    bus = EventBus()
    bus.subscribe("trade.closed", handler_fn)
    bus.subscribe("tick.received", another_handler)
    bus.publish(Event(type="trade.closed", payload=trade))

Para handlers async:
    async def my_handler(event): ...
    bus.subscribe("tick.received", my_handler)
    await bus.publish_async(event)
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import Union

from domains.crypto_coin.core.schemas import Event

Handler = Union[Callable[[Event], None], Callable[[Event], Awaitable[None]]]


class EventBus:
    def __init__(self, logger: logging.Logger | None = None):
        self._handlers: dict[str, list[Handler]] = defaultdict(list)
        self._wildcard: list[Handler] = []
        self._logger = logger or logging.getLogger("event_bus")

    # ── Subscrição ────────────────────────────────────────────

    def subscribe(self, event_type: str, handler: Handler) -> None:
        """Registra handler para um tipo de evento. Use '*' para todos."""
        if event_type == "*":
            self._wildcard.append(handler)
        else:
            self._handlers[event_type].append(handler)

    def unsubscribe(self, event_type: str, handler: Handler) -> None:
        if event_type == "*":
            self._wildcard = [h for h in self._wildcard if h is not handler]
        else:
            self._handlers[event_type] = [
                h for h in self._handlers[event_type] if h is not handler
            ]

    # ── Publicação síncrona ───────────────────────────────────

    def publish(self, event: Event) -> None:
        """Dispara handlers síncronos."""
        for handler in self._handlers.get(event.type, []) + self._wildcard:
            try:
                result = handler(event)
                if asyncio.iscoroutine(result):
                    self._logger.warning(
                        f"Handler async registrado em publish() síncrono — use publish_async(). "
                        f"handler={handler.__name__}, event={event.type}"
                    )
            except Exception as e:
                self._logger.error(f"EventBus error [{event.type}]: {e}", exc_info=True)

    # ── Publicação assíncrona ─────────────────────────────────

    async def publish_async(self, event: Event) -> None:
        """Dispara handlers síncronos e assíncronos."""
        for handler in self._handlers.get(event.type, []) + self._wildcard:
            try:
                result = handler(event)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                self._logger.error(f"EventBus error [{event.type}]: {e}", exc_info=True)

    # ── Utilitários ───────────────────────────────────────────

    def listeners(self, event_type: str) -> int:
        return len(self._handlers.get(event_type, [])) + len(self._wildcard)

    def clear(self) -> None:
        self._handlers.clear()
        self._wildcard.clear()
