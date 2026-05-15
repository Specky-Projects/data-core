from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class RawCollectionResponse(BaseModel):
    id: UUID
    module: str
    source_name: str
    source_type: str | None
    source_id: str | None
    collector_name: str
    collector_version: str
    raw_schema_name: str
    raw_schema_version: str
    target_url: str | None
    endpoint: str | None
    method: str | None
    response_status: int | None
    content_type: str | None
    checksum: str
    collected_at: datetime
    processing_status: str
    error_message: str | None
    metadata_json: dict[str, Any]
    collection_metadata_json: dict[str, Any]

    model_config = ConfigDict(from_attributes=True)
