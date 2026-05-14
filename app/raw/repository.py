from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.raw.models import RawCollection


class RawRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, raw: RawCollection) -> RawCollection:
        self.db.add(raw)
        self.db.flush()
        return raw

    def get(self, raw_id: str) -> RawCollection | None:
        return self.db.get(RawCollection, raw_id)

    def list_rows(
        self,
        *,
        module: str | None = None,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[RawCollection]:
        query = self.db.query(RawCollection)
        if module:
            query = query.filter(RawCollection.module == module)
        if status:
            query = query.filter(RawCollection.processing_status == status)
        return query.order_by(desc(RawCollection.collected_at)).offset(offset).limit(limit).all()

    def pending_for_module(self, module: str, *, limit: int = 100) -> list[RawCollection]:
        return (
            self.db.query(RawCollection)
            .filter(RawCollection.module == module, RawCollection.processing_status == "normalization_pending")
            .order_by(RawCollection.collected_at)
            .limit(limit)
            .all()
        )
