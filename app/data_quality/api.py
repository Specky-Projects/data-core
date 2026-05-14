from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session

from api.deps import db_session
from app.data_quality.models import DataQualityRun
from app.data_quality.services import DataQualityService

router = APIRouter(prefix="/api/v1/data-quality", tags=["data-quality"])


@router.post("/run")
def run_data_quality(
    db: Session = Depends(db_session),
    module: str | None = None,
    source_name: str | None = None,
    limit: int = Query(default=1000, ge=1, le=10000),
) -> dict[str, Any]:
    return DataQualityService(db).run(module=module, source_name=source_name, limit=limit)


@router.get("/runs")
def list_data_quality_runs(
    db: Session = Depends(db_session),
    module: str | None = None,
    limit: int = Query(default=50, ge=1, le=500),
) -> list[dict[str, Any]]:
    query = db.query(DataQualityRun)
    if module:
        query = query.filter(DataQualityRun.module == module)
    rows = query.order_by(desc(DataQualityRun.created_at)).limit(limit).all()
    return [{column.name: getattr(row, column.name) for column in row.__table__.columns} for row in rows]
