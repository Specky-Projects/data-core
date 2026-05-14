from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from api.deps import db_session
from app.analytics.models import (
    CryptoAnalytics,
    ProductPriceAnalytics,
    RealEstateAnalytics,
    SportsOddsAnalytics,
    TradingAnalytics,
)
from app.normalization.models import (
    NormalizedCryptoSnapshot,
    NormalizedMarketCandle,
    NormalizedProduct,
    NormalizedRealEstateListing,
    NormalizedSportsOdd,
    NormalizerVersion,
)
from app.raw.models import CollectorVersion, RawCollection
from app.raw.repository import RawRepository
from app.data_quality.models import DataQualityRun
from database.models import CollectionRun, CollectorError
from scheduler.jobs import MODULE_COLLECTORS

router = APIRouter(prefix="/api/v1", tags=["pipeline"])

NORMALIZED_TABLES = {
    "ecommerce": NormalizedProduct,
    "real_estate": NormalizedRealEstateListing,
    "crypto": NormalizedCryptoSnapshot,
    "trading": NormalizedMarketCandle,
    "sports_odds": NormalizedSportsOdd,
}

ANALYTICS_TABLES = {
    "ecommerce": ProductPriceAnalytics,
    "real_estate": RealEstateAnalytics,
    "crypto": CryptoAnalytics,
    "trading": TradingAnalytics,
    "sports_odds": SportsOddsAnalytics,
}

@router.get("/raw-collections")
def list_raw_collections(
    db: Session = Depends(db_session),
    module: str | None = None,
    status: str | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[dict[str, Any]]:
    rows = RawRepository(db).list_rows(module=module, status=status, limit=limit, offset=offset)
    return [_to_dict(row, exclude={"raw_content", "raw_json"}) for row in rows]


@router.get("/raw-collections/{raw_id}")
def get_raw_collection(raw_id: UUID, db: Session = Depends(db_session)) -> dict[str, Any]:
    raw = RawRepository(db).get(str(raw_id))
    if not raw:
        raise HTTPException(status_code=404, detail="RAW collection not found")
    return _to_dict(raw)


@router.get("/collection-runs")
def list_collection_runs(
    db: Session = Depends(db_session),
    module: str | None = None,
    collector_name: str | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[dict[str, Any]]:
    query = db.query(CollectionRun)
    if module:
        query = query.filter(CollectionRun.module == module)
    if collector_name:
        query = query.filter(CollectionRun.collector_name == collector_name)
    rows = query.order_by(desc(CollectionRun.created_at)).offset(offset).limit(limit).all()
    return [_to_dict(row) for row in rows]


@router.get("/jobs/status")
def jobs_status(db: Session = Depends(db_session)) -> dict[str, Any]:
    latest_runs = (
        db.query(CollectionRun)
        .order_by(desc(CollectionRun.started_at), desc(CollectionRun.created_at))
        .limit(25)
        .all()
    )
    return {
        "modules": [
            {"module": module, "collectors": collectors}
            for module, collectors in sorted(MODULE_COLLECTORS.items())
        ],
        "latest_runs": [_to_dict(run) for run in latest_runs],
    }


@router.get("/collectors/{collector_name}/versions")
def list_collector_versions(collector_name: str, db: Session = Depends(db_session)) -> list[dict[str, Any]]:
    rows = (
        db.query(CollectorVersion)
        .filter(CollectorVersion.collector_name == collector_name)
        .order_by(desc(CollectorVersion.created_at))
        .all()
    )
    return [_to_dict(row) for row in rows]


@router.get("/normalizers")
def list_normalizers(db: Session = Depends(db_session)) -> list[dict[str, Any]]:
    rows = db.query(NormalizerVersion).order_by(NormalizerVersion.module, NormalizerVersion.normalizer_name).all()
    return [_to_dict(row) for row in rows]


@router.get("/normalizers/{normalizer_name}/versions")
def list_normalizer_versions(normalizer_name: str, db: Session = Depends(db_session)) -> list[dict[str, Any]]:
    rows = (
        db.query(NormalizerVersion)
        .filter(NormalizerVersion.normalizer_name == normalizer_name)
        .order_by(desc(NormalizerVersion.created_at))
        .all()
    )
    return [_to_dict(row) for row in rows]


@router.get("/data-quality/summary")
def data_quality_summary(
    db: Session = Depends(db_session),
    normalizer_version: str | None = None,
) -> list[dict[str, Any]]:
    query = db.query(
        DataQualityRun.module,
        DataQualityRun.normalizer_name,
        DataQualityRun.normalizer_version,
        func.sum(DataQualityRun.checked_count),
        func.sum(DataQualityRun.passed_count),
        func.sum(DataQualityRun.failed_count),
    )
    if normalizer_version:
        query = query.filter(DataQualityRun.normalizer_version == normalizer_version)
    rows = query.group_by(
        DataQualityRun.module,
        DataQualityRun.normalizer_name,
        DataQualityRun.normalizer_version,
    ).all()
    return [
        {
            "module": module,
            "normalizer_name": name,
            "normalizer_version": version,
            "checked_count": int(checked or 0),
            "passed_count": int(passed or 0),
            "failed_count": int(failed or 0),
        }
        for module, name, version, checked, passed, failed in rows
    ]


@router.get("/normalized/{module}")
def list_normalized(
    module: str,
    db: Session = Depends(db_session),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[dict[str, Any]]:
    model = NORMALIZED_TABLES.get(module)
    if model is None:
        raise HTTPException(status_code=404, detail="Normalized module not found")
    rows = db.query(model).offset(offset).limit(limit).all()
    return [_to_dict(row) for row in rows]


@router.get("/analytics/{module}")
def list_analytics(
    module: str,
    db: Session = Depends(db_session),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[dict[str, Any]]:
    model = ANALYTICS_TABLES.get(module)
    if model is None:
        raise HTTPException(status_code=404, detail="Analytics module not found")
    rows = db.query(model).offset(offset).limit(limit).all()
    return [_to_dict(row) for row in rows]


@router.get("/pipeline/status")
def pipeline_status(db: Session = Depends(db_session)) -> dict[str, Any]:
    raw_statuses = (
        db.query(RawCollection.module, RawCollection.processing_status, func.count(RawCollection.id))
        .group_by(RawCollection.module, RawCollection.processing_status)
        .all()
    )
    normalized_counts = {
        module: db.query(model).count()
        for module, model in NORMALIZED_TABLES.items()
    }
    analytics_counts = {
        module: db.query(model).count()
        for module, model in ANALYTICS_TABLES.items()
    }
    return {
        "raw": [
            {"module": module, "processing_status": status, "count": count}
            for module, status, count in raw_statuses
        ],
        "normalized": normalized_counts,
        "analytics": analytics_counts,
        "supported_modules": sorted(NORMALIZED_TABLES.keys()),
    }


@router.get("/operations/summary")
def operations_summary(db: Session = Depends(db_session)) -> dict[str, Any]:
    raw_pending = (
        db.query(RawCollection.module, func.count(RawCollection.id))
        .filter(RawCollection.processing_status == "normalization_pending")
        .group_by(RawCollection.module)
        .all()
    )
    raw_failed = (
        db.query(RawCollection.module, func.count(RawCollection.id))
        .filter(RawCollection.processing_status == "normalization_failed")
        .group_by(RawCollection.module)
        .all()
    )
    analytics_pending = {
        module: db.query(model).filter(model.analytics_status == "pending").count()
        for module, model in NORMALIZED_TABLES.items()
        if hasattr(model, "analytics_status")
    }
    latest_quality = (
        db.query(DataQualityRun)
        .order_by(desc(DataQualityRun.created_at))
        .limit(10)
        .all()
    )
    recent_errors = db.query(CollectorError).order_by(desc(CollectorError.created_at)).limit(10).all()
    return {
        "raw_pending_by_module": {module: count for module, count in raw_pending},
        "raw_failed_by_module": {module: count for module, count in raw_failed},
        "analytics_pending_by_module": analytics_pending,
        "latest_quality_runs": [_to_dict(row) for row in latest_quality],
        "recent_collector_errors": [_to_dict(row) for row in recent_errors],
    }


@router.get("/operations/latest-collections")
def latest_collections(
    db: Session = Depends(db_session),
    module: str | None = None,
    limit: int = Query(default=25, ge=1, le=200),
) -> list[dict[str, Any]]:
    query = db.query(CollectionRun)
    if module:
        query = query.filter(CollectionRun.module == module)
    rows = query.order_by(desc(CollectionRun.started_at), desc(CollectionRun.created_at)).limit(limit).all()
    return [_to_dict(row) for row in rows]


@router.get("/operations/raw-pending")
def raw_pending(
    db: Session = Depends(db_session),
    module: str | None = None,
    limit: int = Query(default=50, ge=1, le=500),
) -> list[dict[str, Any]]:
    query = db.query(RawCollection).filter(RawCollection.processing_status == "normalization_pending")
    if module:
        query = query.filter(RawCollection.module == module)
    rows = query.order_by(desc(RawCollection.collected_at)).limit(limit).all()
    return [_to_dict(row, exclude={"raw_content", "raw_json"}) for row in rows]


@router.get("/operations/normalization-failures")
def normalization_failures(
    db: Session = Depends(db_session),
    module: str | None = None,
    limit: int = Query(default=50, ge=1, le=500),
) -> list[dict[str, Any]]:
    query = db.query(RawCollection).filter(RawCollection.processing_status == "normalization_failed")
    if module:
        query = query.filter(RawCollection.module == module)
    rows = query.order_by(desc(RawCollection.collected_at)).limit(limit).all()
    return [_to_dict(row, exclude={"raw_content", "raw_json"}) for row in rows]


@router.get("/operations/analytics-pending")
def analytics_pending(
    module: str,
    db: Session = Depends(db_session),
    limit: int = Query(default=50, ge=1, le=500),
) -> list[dict[str, Any]]:
    model = NORMALIZED_TABLES.get(module)
    if model is None:
        raise HTTPException(status_code=404, detail="Normalized module not found")
    if not hasattr(model, "analytics_status"):
        return []
    rows = db.query(model).filter(model.analytics_status == "pending").limit(limit).all()
    return [_to_dict(row) for row in rows]


@router.get("/operations/collector-errors")
def collector_errors(
    db: Session = Depends(db_session),
    collector_name: str | None = None,
    limit: int = Query(default=50, ge=1, le=500),
) -> list[dict[str, Any]]:
    query = db.query(CollectorError)
    if collector_name:
        query = query.filter(CollectorError.collector_name == collector_name)
    rows = query.order_by(desc(CollectorError.created_at)).limit(limit).all()
    return [_to_dict(row) for row in rows]


def _to_dict(row: object, *, exclude: set[str] | None = None) -> dict[str, Any]:
    exclude = exclude or set()
    data: dict[str, Any] = {}
    for column in row.__table__.columns:
        if column.name in exclude:
            continue
        attr_name = "metadata_" if column.name == "metadata" and hasattr(row, "metadata_") else column.name
        data[column.name] = getattr(row, attr_name)
    return data
