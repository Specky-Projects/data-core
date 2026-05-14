import asyncio
import logging

from app.modules.real_estate.collectors import ApolarCollector
from database.session import SessionLocal

logger = logging.getLogger(__name__)


def run_real_estate_daily_collection() -> None:
    async def _run() -> None:
        db = SessionLocal()
        try:
            result = await ApolarCollector(db).run()
            logger.info("Real estate scheduled collection finished", extra=result.__dict__)
        finally:
            db.close()

    asyncio.run(_run())

