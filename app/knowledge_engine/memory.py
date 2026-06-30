"""ScientificMemory — append-only event log for Knowledge lifecycle.

NEVER modifies existing records. NO delete. NO update.
"""
from __future__ import annotations

from datetime import datetime


class ScientificMemory:
    def __init__(self) -> None:
        self._events: list[dict] = []  # append-only

    def record(self, event_type: str, knowledge_id: str, payload: dict) -> None:
        self._events.append(
            {
                "event_type": event_type,
                "knowledge_id": knowledge_id,
                "payload": payload,
                "recorded_at": datetime.utcnow().isoformat(),
            }
        )

    def history(self, knowledge_id: str) -> list[dict]:
        return [e for e in self._events if e["knowledge_id"] == knowledge_id]

    def all_events(self) -> list[dict]:
        return list(self._events)

    def count(self) -> int:
        return len(self._events)

    # Intentionally NO delete() or update() methods.
    # ScientificMemory is append-only by design.
