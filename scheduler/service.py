import logging

from apscheduler.schedulers.background import BackgroundScheduler

from collectors.registry import registry
from core.config import settings
from scheduler.jobs import run_collector_job

logger = logging.getLogger(__name__)


def create_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone=settings.scheduler_timezone)

    for collector_type in registry.all():
        metadata = collector_type.metadata
        scheduler.add_job(
            run_collector_job,
            "interval",
            minutes=metadata.default_interval_minutes,
            args=[metadata.name],
            id=f"collector:{metadata.name}",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )

    return scheduler


def start_scheduler(scheduler: BackgroundScheduler) -> None:
    if settings.scheduler_enabled and not scheduler.running:
        scheduler.start()
        logger.info("Scheduler started")


def stop_scheduler(scheduler: BackgroundScheduler) -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
