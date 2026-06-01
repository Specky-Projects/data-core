from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.raw.service import RawCollectionInput, RawService
from database.models import CollectorDomain
from utils.sanitization import sanitize_for_postgres


@dataclass(frozen=True)
class CollectorMetadata:
    name: str
    domain: CollectorDomain
    source: str
    description: str
    default_interval_minutes: int = 60
    collector_version: str = "1.0.0"
    raw_schema_name: str = "genericJson"
    raw_schema_version: str = "1.0.0"
    # schedulable=False → collector existe para documentação/testes mas NÃO deve ser
    # agendado automaticamente (ex: mocks de demo, placeholders sem fonte real).
    # O scheduler verifica este flag antes de criar o job automático.
    schedulable: bool = True


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
        """Collect source data and return raw payloads."""

    def save_raw(self, db: Session, items: list[CollectedItem]) -> int:
        raw_service = RawService(db)
        saved = 0
        for item in items:
            raw = raw_service.save(
                RawCollectionInput(
                    module=self.raw_module,
                    source_id=item.external_id,
                    source_name=self.metadata.source,
                    collector_name=self.metadata.name,
                    collector_version=self.metadata.collector_version,
                    raw_schema_name=self.metadata.raw_schema_name,
                    raw_schema_version=self.metadata.raw_schema_version,
                    target_url=item.source_url,
                    endpoint=item.source_url,
                    method="GET",
                    content_type="application/json",
                    raw_json=sanitize_for_postgres(item.payload),
                    metadata_json={
                        "collector": self.metadata.name,
                        **sanitize_for_postgres(item.metadata),
                    },
                )
            )
            saved += 1 if getattr(raw, "_raw_was_created", True) else 0
        return saved

    async def run(self, db: Session) -> int:
        items = await self.collect()
        return self.save_raw(db, items)

    @property
    def raw_module(self) -> str:
        if self.metadata.domain.value == "sports_betting":
            return "sports_odds"
        return self.metadata.domain.value
