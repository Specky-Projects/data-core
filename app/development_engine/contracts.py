"""Development Engine — Contracts."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class ReuseAction(StrEnum):
    REUSE = "REUSE"
    EXTEND = "EXTEND"
    GENERALIZE = "GENERALIZE"
    CREATE_NEW = "CREATE_NEW"


@dataclass
class ReuseCheckResult:
    action: ReuseAction
    candidates: list[dict]
    rationale: str
    evidence: list[str]
    advisory_only: bool = True

    def __post_init__(self) -> None:
        assert self.advisory_only is True


@dataclass
class DevelopmentCapabilityResult:
    result_id: str
    capability_name: str
    outputs: dict[str, Any]
    advisory_only: bool = True
    produced_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self) -> None:
        assert self.advisory_only is True
        assert isinstance(self.outputs, dict)
