from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from database.models import CollectorDomain, RunStatus


class HealthResponse(BaseModel):
    status: str
    app: str
    environment: str


class CollectorResponse(BaseModel):
    name: str
    domain: CollectorDomain
    source: str
    description: str
    default_interval_minutes: int


class RunCollectorResponse(BaseModel):
    id: UUID
    collector_name: str
    domain: CollectorDomain
    source: str
    status: RunStatus
    started_at: datetime | None
    finished_at: datetime | None
    items_collected: int
    error_message: str | None

    model_config = ConfigDict(from_attributes=True)


class CollectedRecordResponse(BaseModel):
    id: UUID
    collector_name: str
    domain: CollectorDomain
    source: str
    external_id: str | None
    source_url: str | None
    payload: dict[str, Any]
    collected_at: datetime

    model_config = ConfigDict(from_attributes=True)
