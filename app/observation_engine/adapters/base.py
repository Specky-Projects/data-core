"""Base protocol for all observation adapters."""
from __future__ import annotations

from typing import Protocol

from app.observation_engine.contracts import ObservationRecord


class ObservationAdapter(Protocol):
    adapter_name: str
    project: str
    domain: str

    def collect(self) -> list[ObservationRecord]: ...
    def health(self) -> dict: ...
