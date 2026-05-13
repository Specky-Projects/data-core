import asyncio
import logging

from database.session import SessionLocal
from workers.collector_worker import run_collector_by_name

logger = logging.getLogger(__name__)


def run_collector_job(collector_name: str) -> None:
    async def _run() -> None:
        db = SessionLocal()
        try:
            await run_collector_by_name(collector_name, db)
        finally:
            db.close()

    logger.info("Starting scheduled collector", extra={"collector": collector_name})
    asyncio.run(_run())
