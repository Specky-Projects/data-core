"""BaseAdapter — shared contract for every project adapter.

An adapter converts a project's raw event dict into a ``UniversalEvent`` and
delegates to the Universal Observation Runtime. It adds no scientific logic of
its own; it only *names the facts* a project already produced.
"""
from __future__ import annotations

from typing import Any, Iterable

from app.universal_platform.events import UniversalEvent
from app.universal_platform.runtime import (
    UniversalObservationRecord,
    UniversalObservationRuntime,
)


class BaseAdapter:
    """Read-only, advisory, shadow-mode bridge from a project to the runtime."""

    PROJECT: str = "unknown"
    DOMAIN: str = "GENERIC"

    SHADOW_MODE = True
    READ_ONLY = True
    ADVISORY_ONLY = True

    def __init__(self, runtime: UniversalObservationRuntime | None = None) -> None:
        self.runtime = runtime or UniversalObservationRuntime()

    # subclasses implement the project-specific normalisation only
    def to_event(self, raw: dict[str, Any]) -> UniversalEvent:  # pragma: no cover
        raise NotImplementedError

    def observe(self, raw: dict[str, Any]) -> UniversalObservationRecord:
        assert self.READ_ONLY and self.ADVISORY_ONLY and self.SHADOW_MODE, (
            "adapters must remain read-only / advisory / shadow"
        )
        return self.runtime.observe(self.to_event(raw))

    def observe_many(
        self, raws: Iterable[dict[str, Any]]
    ) -> list[UniversalObservationRecord]:
        return [self.observe(r) for r in raws]

    def descriptor(self) -> dict[str, Any]:
        return {
            "project": self.PROJECT,
            "domain": self.DOMAIN,
            "shadow_mode": self.SHADOW_MODE,
            "read_only": self.READ_ONLY,
            "advisory_only": self.ADVISORY_ONLY,
        }
