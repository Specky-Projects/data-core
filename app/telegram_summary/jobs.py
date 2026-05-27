"""Scheduler job functions for the Telegram Longitudinal Summary layer.

Jobs are intentionally thin — all logic lives in TelegramSummaryService.
Each job:
  1. Checks feature flags (telegram_summary_enabled + type-specific flag)
  2. Opens a DB session
  3. Calls the relevant service method
  4. Catches and logs all exceptions — NEVER crashes the scheduler

Registered in scheduler/service.py via create_scheduler().
"""

from __future__ import annotations

import logging

from core.config import settings
from database.session import SessionLocal

logger = logging.getLogger(__name__)


def hourly_operational_summary_job() -> None:
    """Send the operational health summary + check for alerts (runs every hour)."""
    if not settings.telegram_summary_enabled:
        logger.debug("telegram_summary: master switch off — skipping hourly job")
        return

    from app.telegram_summary.services.telegram_summary_service import TelegramSummaryService
    svc = TelegramSummaryService()

    if settings.telegram_summary_operational_enabled:
        try:
            with SessionLocal() as db:
                svc.send_operational_summary(db)
        except Exception:
            logger.exception("telegram_summary: hourly operational send failed")

    if settings.telegram_summary_alerts_enabled:
        try:
            with SessionLocal() as db:
                n = svc.check_and_send_alerts(db)
                if n > 0:
                    logger.info("telegram_summary: sent %d alert(s)", n)
        except Exception:
            logger.exception("telegram_summary: hourly alert check failed")


def six_hour_quant_summary_job() -> None:
    """Send the quant/adaptive intelligence summary (runs every 6 hours)."""
    if not settings.telegram_summary_enabled or not settings.telegram_summary_quant_enabled:
        logger.debug("telegram_summary: quant job disabled — skipping")
        return

    from app.telegram_summary.services.telegram_summary_service import TelegramSummaryService
    try:
        with SessionLocal() as db:
            TelegramSummaryService().send_quant_summary(db)
    except Exception:
        logger.exception("telegram_summary: 6h quant send failed")


def daily_longitudinal_summary_job() -> None:
    """Send the longitudinal 24h vs 7d digest (runs daily via cron)."""
    if not settings.telegram_summary_enabled or not settings.telegram_summary_longitudinal_enabled:
        logger.debug("telegram_summary: longitudinal job disabled — skipping")
        return

    from app.telegram_summary.services.telegram_summary_service import TelegramSummaryService
    try:
        with SessionLocal() as db:
            TelegramSummaryService().send_longitudinal_summary(db)
    except Exception:
        logger.exception("telegram_summary: daily longitudinal send failed")
