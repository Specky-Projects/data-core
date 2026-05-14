import asyncio
import logging

from app.analytics.registry import analytics_registry
from app.modules.registry import register_pipeline_modules
from app.normalization.registry import normalizer_registry
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


def collect_raw_job(collector_name: str) -> None:
    logger.info("Starting RAW collection job", extra={"collector": collector_name})
    run_collector_job(collector_name)


def normalize_job(module: str | None = None, limit: int = 100) -> None:
    register_pipeline_modules()
    db = SessionLocal()
    try:
        modules = [module] if module else normalizer_registry.modules()
        for module_name in modules:
            normalizer_types = normalizer_registry.all().get(module_name, [])
            for normalizer_type in normalizer_types:
                logger.info(
                    "Starting normalization job",
                    extra={
                        "pipeline_module": module_name,
                        "normalizer": normalizer_type.__name__,
                    },
                )
                normalizer_type(db).run(limit=limit)
    finally:
        db.close()


MODULE_COLLECTORS = {
    "ecommerce": ["ecommerce.generic_product"],
    "real_estate": ["real_estate.generic_listing"],
    "sports_odds": ["sports_betting.generic_odds"],
    "crypto": ["crypto.generic_price", "crypto.crypto_coin_ohlcv"],
    "trading": [],
}

SOURCE_COLLECTORS = {
    "generic_marketplace": "ecommerce.generic_product",
    "generic_real_estate": "real_estate.generic_listing",
    "generic_bookmaker": "sports_betting.generic_odds",
    "generic_exchange": "crypto.generic_price",
    "crypto_coin_exchange": "crypto.crypto_coin_ohlcv",
}


def run_module_collectors_job(module: str, source: str | None = None) -> None:
    collectors = MODULE_COLLECTORS.get(module, [])
    if source:
        selected = SOURCE_COLLECTORS.get(source)
        collectors = [selected] if selected and selected in collectors else []
    for collector_name in collectors:
        collect_raw_job(collector_name)


def run_ecommerce_collectors_job(source: str | None = None) -> None:
    run_module_collectors_job("ecommerce", source=source)


def run_real_estate_collectors_job(source: str | None = None) -> None:
    run_module_collectors_job("real_estate", source=source)


def run_sports_odds_collectors_job(source: str | None = None) -> None:
    run_module_collectors_job("sports_odds", source=source)


def run_crypto_collectors_job(source: str | None = None) -> None:
    run_module_collectors_job("crypto", source=source)


def run_trading_collectors_job(source: str | None = None) -> None:
    run_module_collectors_job("trading", source=source)


def analytics_job(module: str | None = None, limit: int = 100) -> None:
    register_pipeline_modules()
    db = SessionLocal()
    try:
        modules = [module] if module else analytics_registry.modules()
        for module_name in modules:
            processor_type = analytics_registry.get(module_name)
            if not processor_type:
                continue
            logger.info("Starting analytics job", extra={"pipeline_module": module_name})
            processor_type(db).run(limit=limit)
    finally:
        db.close()
