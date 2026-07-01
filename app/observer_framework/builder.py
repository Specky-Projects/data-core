"""RuntimeSnapshotBuilder — wraps the existing ObservationEngine.

This module implements NO new production access. It only serialises what
app.observation_engine.engine.ObservationEngine already produces (today, a mix
of real and synthetic-stub adapters — see COLLECTOR_SPECIFICATION.md) into a
RuntimeSnapshotContract.

build_revision reuses the exact same env vars app/main.py's /build-info
endpoint already reads (VCS_REF / SOURCE_COMMIT / COMMIT_SHA) — no new
convention introduced.
"""
from __future__ import annotations

import os

from app.business_os_platform import BUSINESS_OS_PLATFORM_VERSION
from app.observation_engine.engine import ObservationEngine
from app.observer_framework.snapshot_contract import RuntimeSnapshotContract

BUILDER_SOURCE = "business-os-observation-engine"


def _build_revision() -> str | None:
    return os.getenv("VCS_REF") or os.getenv("SOURCE_COMMIT") or os.getenv("COMMIT_SHA")


class RuntimeSnapshotBuilder:
    def __init__(self, engine: ObservationEngine | None = None) -> None:
        self.engine = engine or ObservationEngine()

    def build(self) -> RuntimeSnapshotContract:
        records = self.engine.collect_all()
        adapter_health = self.engine.health()
        return RuntimeSnapshotContract.create(
            source=BUILDER_SOURCE,
            records=records,
            adapter_health=adapter_health,
            runtime_version=BUSINESS_OS_PLATFORM_VERSION,
            build_revision=_build_revision(),
        )
