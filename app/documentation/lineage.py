from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.documentation.models import DataLineage
from app.raw.models import RawCollection


class LineageService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def record_normalized(
        self,
        *,
        raw: RawCollection,
        normalizer_name: str,
        normalizer_version: str,
        normalized_record_type: str,
        normalized_record_id: UUID,
        metadata: dict[str, Any] | None = None,
    ) -> DataLineage:
        existing = (
            self.db.query(DataLineage)
            .filter(
                DataLineage.raw_collection_id == raw.id,
                DataLineage.normalized_record_type == normalized_record_type,
                DataLineage.normalized_record_id == normalized_record_id,
                DataLineage.analytics_record_type.is_(None),
                DataLineage.analytics_record_id.is_(None),
            )
            .one_or_none()
        )
        if existing:
            return existing
        row = DataLineage(
            module=raw.module,
            source_name=raw.source_name,
            collector_name=raw.collector_name,
            collector_version=raw.collector_version,
            raw_schema_name=raw.raw_schema_name,
            raw_schema_version=raw.raw_schema_version,
            raw_collection_id=raw.id,
            normalizer_name=normalizer_name,
            normalizer_version=normalizer_version,
            normalized_record_type=normalized_record_type,
            normalized_record_id=normalized_record_id,
            metadata_json=metadata or {},
        )
        self.db.add(row)
        self.db.flush()
        return row

    def attach_analytics(
        self,
        *,
        normalized_record_type: str,
        normalized_record_id: UUID,
        analytics_processor_name: str,
        analytics_processor_version: str,
        analytics_record_type: str,
        analytics_record_id: UUID,
        metadata: dict[str, Any] | None = None,
    ) -> int:
        rows = (
            self.db.query(DataLineage)
            .filter(
                DataLineage.normalized_record_type == normalized_record_type,
                DataLineage.normalized_record_id == normalized_record_id,
            )
            .all()
        )
        updated = 0
        for row in rows:
            duplicate = (
                self.db.query(DataLineage)
                .filter(
                    DataLineage.id != row.id,
                    DataLineage.raw_collection_id == row.raw_collection_id,
                    DataLineage.normalized_record_type == normalized_record_type,
                    DataLineage.normalized_record_id == normalized_record_id,
                    DataLineage.analytics_record_type == analytics_record_type,
                    DataLineage.analytics_record_id == analytics_record_id,
                )
                .one_or_none()
            )
            if duplicate:
                self.db.delete(row)
                continue
            row.analytics_processor_name = analytics_processor_name
            row.analytics_processor_version = analytics_processor_version
            row.analytics_record_type = analytics_record_type
            row.analytics_record_id = analytics_record_id
            row.metadata_json = {**(row.metadata_json or {}), **(metadata or {})}
            updated += 1
        return updated

    def lineage_for_raw(self, raw_collection_id: UUID) -> dict[str, Any]:
        rows = (
            self.db.query(DataLineage)
            .filter(DataLineage.raw_collection_id == raw_collection_id)
            .order_by(DataLineage.created_at)
            .all()
        )
        if not rows:
            return {"raw_collection": {"id": str(raw_collection_id)}, "normalized_records": [], "analytics": []}

        first = rows[0]
        normalized = []
        analytics = []
        for row in rows:
            if row.normalized_record_id:
                normalized.append(
                    {
                        "id": str(row.normalized_record_id),
                        "type": row.normalized_record_type,
                        "normalizer_name": row.normalizer_name,
                        "normalizer_version": row.normalizer_version,
                    }
                )
            if row.analytics_record_id:
                analytics.append(
                    {
                        "id": str(row.analytics_record_id),
                        "type": row.analytics_record_type,
                        "analytics_name": row.analytics_processor_name,
                        "analytics_version": row.analytics_processor_version,
                    }
                )
        return {
            "raw_collection": {
                "id": str(raw_collection_id),
                "collector_name": first.collector_name,
                "collector_version": first.collector_version,
                "raw_schema_name": first.raw_schema_name,
                "raw_schema_version": first.raw_schema_version,
                "source_name": first.source_name,
                "module": first.module,
            },
            "normalized_records": normalized,
            "analytics": analytics,
        }
