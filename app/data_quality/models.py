import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from database.models import Base


class DataQualityRun(Base):
    __tablename__ = "data_quality_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    module: Mapped[str] = mapped_column(String(80), index=True)
    source_name: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    normalizer_name: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    normalizer_version: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    raw_schema_name: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    raw_schema_version: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    checked_count: Mapped[int] = mapped_column(Integer, default=0)
    passed_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, default=0)
    quality_score: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="completed", index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
