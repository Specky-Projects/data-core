import asyncio
import logging

from app.modules.sports_odds.collectors import NbaOddsCollector
from database.session import SessionLocal

logger = logging.getLogger(__name__)


def run_sports_odds_recurring_collection() -> None:
    async def _run() -> None:
        db = SessionLocal()
        try:
            result = await NbaOddsCollector(db).run()
            logger.info("Sports odds scheduled collection finished", extra=result.__dict__)
        finally:
            db.close()

    asyncio.run(_run())
