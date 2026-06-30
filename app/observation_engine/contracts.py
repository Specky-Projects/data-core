"""Observation Engine — Contracts.

ObservationRecord is a higher-level wrapper over ObservationContract,
adding operational metadata (health, severity) for the Business OS.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from app.scientific_identity.contract import stable_hash


OBSERVATION_RECORD_VERSION = "observation-record-v1"


class ObservationSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class ObservationHealth(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    CRITICAL = "CRITICAL"
    UNKNOWN = "UNKNOWN"


@dataclass
class ObservationRecord:
    observation_id: str
    scientific_id: str
    lineage_id: str
    project: str
    domain: str
    source: str
    severity: ObservationSeverity
    health: ObservationHealth
    evidence: list[str]
    metrics: dict[str, float]
    timestamp: datetime
    advisory_only: bool = True
    version: str = OBSERVATION_RECORD_VERSION

    def __post_init__(self) -> None:
        assert self.advisory_only is True, "ObservationRecord must always be advisory_only"
        assert self.observation_id, "observation_id is required"
        assert self.project, "project is required"
        assert self.source, "source is required"
