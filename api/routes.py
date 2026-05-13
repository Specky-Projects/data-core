from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc
from sqlalchemy.orm import Session

from api.deps import db_session
from api.schemas import CollectedRecordResponse, CollectorResponse, RunCollectorResponse
from collectors.registry import registry
from database.models import CollectedRecord, CollectionRun
from workers.collector_worker import run_collector_by_name

router = APIRouter(prefix="/api/v1")


@router.get("/collectors", response_model=list[CollectorResponse])
def list_collectors() -> list[CollectorResponse]:
    return [
        CollectorResponse(
            name=collector.metadata.name,
            domain=collector.metadata.domain,
            source=collector.metadata.source,
            description=collector.metadata.description,
            default_interval_minutes=collector.metadata.default_interval_minutes,
        )
        for collector in registry.all()
    ]


@router.post(
    "/collectors/{collector_name}/run",
    response_model=RunCollectorResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def run_collector(collector_name: str, db: Session = Depends(db_session)) -> CollectionRun:
    if collector_name not in registry.names():
        raise HTTPException(status_code=404, detail="Collector not found")
    return await run_collector_by_name(collector_name, db)


@router.get("/runs", response_model=list[RunCollectorResponse])
def list_runs(
    db: Session = Depends(db_session),
    limit: int = Query(default=50, ge=1, le=500),
) -> list[CollectionRun]:
    return (
        db.query(CollectionRun)
        .order_by(desc(CollectionRun.created_at))
        .limit(limit)
        .all()
    )


@router.get("/records", response_model=list[CollectedRecordResponse])
def list_records(
    db: Session = Depends(db_session),
    limit: int = Query(default=50, ge=1, le=500),
) -> list[CollectedRecord]:
    return (
        db.query(CollectedRecord)
        .order_by(desc(CollectedRecord.collected_at))
        .limit(limit)
        .all()
    )
