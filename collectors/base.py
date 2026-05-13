from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from database.models import CollectorDomain


@dataclass(frozen=True)
class CollectorMetadata:
    name: str
    domain: CollectorDomain
    source: str
    description: str
    default_interval_minutes: int = 60


@dataclass(frozen=True)
class CollectedItem:
    payload: dict[str, Any]
    external_id: str | None = None
    source_url: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseCollector(ABC):
    metadata: CollectorMetadata

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or {}

    @abstractmethod
    async def collect(self) -> list[CollectedItem]:
        """Collect source data and return normalized raw payloads."""
