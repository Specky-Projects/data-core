import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from database.models import Base


class DataLineage(Base):
    __tablename__ = "data_lineage"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    module: Mapped[str] = mapped_column(String(80), index=True)
    source_name: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    collector_name: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    collector_version: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    raw_schema_name: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    raw_schema_version: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    raw_collection_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    normalizer_name: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    normalizer_version: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    normalized_record_type: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    normalized_record_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    analytics_processor_name: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    analytics_processor_version: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    analytics_record_type: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    analytics_record_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)

    __table_args__ = (
        UniqueConstraint(
            "raw_collection_id",
            "normalized_record_type",
            "normalized_record_id",
            "analytics_record_type",
            "analytics_record_id",
            name="uq_data_lineage_path",
        ),
        Index("ix_data_lineage_raw_normalized", "raw_collection_id", "normalized_record_id"),
    )


class SchemaDocumentation(Base):
    __tablename__ = "schema_documentation"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    module: Mapped[str] = mapped_column(String(80), index=True)
    schema_type: Mapped[str] = mapped_column(String(80), index=True)
    schema_name: Mapped[str] = mapped_column(String(160), index=True)
    schema_version: Mapped[str] = mapped_column(String(40), index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    fields_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    examples_json: Mapped[dict[str, Any] | list[Any]] = mapped_column(JSONB, default=dict)
    validation_rules_json: Mapped[dict[str, Any] | list[Any]] = mapped_column(JSONB, default=dict)
    relationships_json: Mapped[dict[str, Any] | list[Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("module", "schema_type", "schema_name", "schema_version", name="uq_schema_documentation_identity"),
    )


class EntityRelationship(Base):
    __tablename__ = "entity_relationships"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    module: Mapped[str] = mapped_column(String(80), index=True)
    source_entity: Mapped[str] = mapped_column(String(160), index=True)
    target_entity: Mapped[str] = mapped_column(String(160), index=True)
    relationship_type: Mapped[str] = mapped_column(String(80), index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("module", "source_entity", "target_entity", "relationship_type", name="uq_entity_relationship_identity"),
    )


class CollectorDocumentation(Base):
    __tablename__ = "collector_documentation"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    module: Mapped[str] = mapped_column(String(80), index=True)
    source_name: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    collector_name: Mapped[str] = mapped_column(String(160), index=True)
    collector_version: Mapped[str] = mapped_column(String(40), index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    supported_sources_json: Mapped[dict[str, Any] | list[Any]] = mapped_column(JSONB, default=dict)
    supported_methods_json: Mapped[dict[str, Any] | list[Any]] = mapped_column(JSONB, default=dict)
    raw_schemas_generated_json: Mapped[dict[str, Any] | list[Any]] = mapped_column(JSONB, default=dict)
    limitations_json: Mapped[dict[str, Any] | list[Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("collector_name", "collector_version", "source_name", name="uq_collector_documentation_identity"),
    )


class NormalizerDocumentation(Base):
    __tablename__ = "normalizer_documentation"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    module: Mapped[str] = mapped_column(String(80), index=True)
    normalizer_name: Mapped[str] = mapped_column(String(160), index=True)
    normalizer_version: Mapped[str] = mapped_column(String(40), index=True)
    supported_raw_schemas_json: Mapped[dict[str, Any] | list[Any]] = mapped_column(JSONB, default=dict)
    generated_entities_json: Mapped[dict[str, Any] | list[Any]] = mapped_column(JSONB, default=dict)
    validation_rules_json: Mapped[dict[str, Any] | list[Any]] = mapped_column(JSONB, default=dict)
    quality_expectations_json: Mapped[dict[str, Any] | list[Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("normalizer_name", "normalizer_version", name="uq_normalizer_documentation_identity"),
    )


class AnalyticsDocumentation(Base):
    __tablename__ = "analytics_documentation"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    module: Mapped[str] = mapped_column(String(80), index=True)
    analytics_name: Mapped[str] = mapped_column(String(160), index=True)
    analytics_version: Mapped[str] = mapped_column(String(40), index=True)
    input_entities_json: Mapped[dict[str, Any] | list[Any]] = mapped_column(JSONB, default=dict)
    output_entities_json: Mapped[dict[str, Any] | list[Any]] = mapped_column(JSONB, default=dict)
    generated_metrics_json: Mapped[dict[str, Any] | list[Any]] = mapped_column(JSONB, default=dict)
    dependencies_json: Mapped[dict[str, Any] | list[Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("analytics_name", "analytics_version", name="uq_analytics_documentation_identity"),
    )


class DataOwner(Base):
    __tablename__ = "data_owners"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    module: Mapped[str] = mapped_column(String(80), index=True)
    owner_name: Mapped[str] = mapped_column(String(160), index=True)
    technical_contact: Mapped[str | None] = mapped_column(String(255), nullable=True)
    business_contact: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)

    __table_args__ = (
        UniqueConstraint("module", "owner_name", name="uq_data_owner_identity"),
    )


class DataSla(Base):
    __tablename__ = "data_slas"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    module: Mapped[str] = mapped_column(String(80), index=True)
    source_name: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    freshness_sla: Mapped[str] = mapped_column(String(120), default="not_defined")
    availability_sla: Mapped[str | None] = mapped_column(String(120), nullable=True)
    quality_sla: Mapped[str | None] = mapped_column(String(120), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)

    __table_args__ = (
        UniqueConstraint("module", "source_name", name="uq_data_sla_identity"),
    )


class DataContract(Base):
    __tablename__ = "data_contracts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    module: Mapped[str] = mapped_column(String(80), index=True)
    source_name: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    contract_name: Mapped[str] = mapped_column(String(160), index=True)
    contract_version: Mapped[str] = mapped_column(String(40), default="1.0.0", index=True)
    owner_name: Mapped[str] = mapped_column(String(160), default="data-platform", index=True)
    freshness_sla: Mapped[str] = mapped_column(String(120), default="not_defined")
    criticality: Mapped[str] = mapped_column(String(40), default="medium", index=True)
    status: Mapped[str] = mapped_column(String(40), default="draft", index=True)
    raw_required: Mapped[bool] = mapped_column(Boolean, default=True)
    lineage_required: Mapped[bool] = mapped_column(Boolean, default=True)
    quality_required: Mapped[bool] = mapped_column(Boolean, default=True)
    schema_rules_json: Mapped[dict[str, Any] | list[Any]] = mapped_column(JSONB, default=dict)
    quality_rules_json: Mapped[dict[str, Any] | list[Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)

    __table_args__ = (
        UniqueConstraint("module", "source_name", "contract_name", "contract_version", name="uq_data_contract_identity"),
    )
