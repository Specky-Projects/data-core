"""FastAPI router for operational watchdog endpoints.

Routes
──────
POST /api/v1/watchdog/report/telegram-published  ← poupi-baby callback
POST /api/v1/watchdog/telegram-alert             ← Alertmanager webhook → Telegram
GET  /api/v1/watchdog/status                     ← current status (last run)
GET  /api/v1/watchdog/runs                       ← run history
GET  /api/v1/watchdog/alerts                     ← aggregated alerts from last run
POST /api/v1/watchdog/heartbeat/send             ← manual trigger heartbeat
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.watchdog.models import TelegramPublicationEvent, WatchdogRun
from database.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/watchdog", tags=["watchdog"])


# ── Alertmanager webhook → Telegram ──────────────────────────────────────────

class _AlertmanagerAlert(BaseModel):
    """Single alert within an Alertmanager webhook payload."""
    status: str = "unknown"  # "firing" | "resolved"
    labels: dict[str, Any] = {}
    annotations: dict[str, Any] = {}
    startsAt: str = ""
    endsAt: str = ""
    generatorURL: str = ""


class AlertmanagerWebhookPayload(BaseModel):
    """Alertmanager POST /webhook body (v4 format)."""
    version: str = "4"
    groupKey: str = ""
    status: str = "firing"  # "firing" | "resolved"
    receiver: str = ""
    groupLabels: dict[str, Any] = {}
    commonLabels: dict[str, Any] = {}
    commonAnnotations: dict[str, Any] = {}
    externalURL: str = ""
    alerts: list[_AlertmanagerAlert] = []


def _format_alertmanager_telegram(payload: AlertmanagerWebhookPayload) -> str:
    """Format an Alertmanager webhook payload as a Telegram message."""
    emoji = "🔴" if payload.status == "firing" else "✅"
    lines: list[str] = [f"{emoji} *[ALERTMANAGER] {payload.status.upper()}*"]

    if payload.commonLabels:
        severity = payload.commonLabels.get("severity", "unknown")
        lines.append(f"Severity: `{severity}`")

    for alert in payload.alerts:
        alert_name = alert.labels.get("alertname", "?")
        summary = alert.annotations.get("summary", alert_name)
        description = alert.annotations.get("description", "")
        service = alert.labels.get("service", alert.labels.get("job", ""))
        status_icon = "🔴" if alert.status == "firing" else "✅"
        lines.append(f"\n{status_icon} *{alert_name}*")
        if service:
            lines.append(f"  Service: `{service}`")
        lines.append(f"  {summary}")
        if description and description != summary:
            lines.append(f"  _{description}_")

    lines.append(f"\n⏱ {datetime.now(tz=timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    return "\n".join(lines)


def _send_telegram_message(text: str) -> bool:
    """Send a Telegram message using the configured bot token and chat."""
    import urllib.request
    import json as json_lib
    from core.config import settings

    if not settings.telegram_enabled or not settings.telegram_bot_token:
        logger.warning("telegram-alert: Telegram not configured — skipping send")
        return False

    chat_id = settings.telegram_system_chat_id or settings.telegram_chat_id
    if not chat_id:
        logger.warning("telegram-alert: no chat_id configured")
        return False

    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    body = json_lib.dumps({
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }).encode()

    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            ok = resp.getcode() == 200
            if not ok:
                logger.warning("telegram-alert: bot API returned %d", resp.getcode())
            return ok
    except Exception as exc:
        logger.error("telegram-alert: failed to send message: %s", exc)
        return False


@router.post(
    "/telegram-alert",
    status_code=200,
    summary="Alertmanager webhook → Telegram (critical alerts only)",
)
def alertmanager_telegram_alert(payload: AlertmanagerWebhookPayload) -> dict[str, Any]:
    """Receive an Alertmanager webhook payload and forward it to Telegram.

    Called by Alertmanager's `telegram-critical` receiver when a rule with
    `channel: telegram` label fires or resolves. Always returns 200 so that
    Alertmanager does not retry on transient send failures.
    """
    logger.info(
        "telegram-alert: received groupKey=%s status=%s alerts=%d",
        payload.groupKey, payload.status, len(payload.alerts),
    )

    if not payload.alerts:
        return {"sent": False, "reason": "no alerts in payload"}

    message = _format_alertmanager_telegram(payload)
    sent = _send_telegram_message(message)

    logger.info("telegram-alert: sent=%s", sent)
    return {
        "sent": sent,
        "status": payload.status,
        "alerts": len(payload.alerts),
        "received_at": datetime.now(tz=timezone.utc).isoformat(),
    }


# ── Request / Response schemas ────────────────────────────────────────────────

class TelegramPublishReport(BaseModel):
    """Payload sent by poupi-baby after each Telegram publish attempt."""

    group_id: str | None = None
    product_id: str | None = None
    offer_id: str | None = None
    marketplace: str | None = None
    price: float | None = None
    deal_score: float | None = None
    status: str                     # "sent" | "failed" | "rate_limited" | "skipped"
    fail_reason: str | None = None
    reported_by: str | None = "poupi-baby"


# ── POST /report/telegram-published ──────────────────────────────────────────

@router.post(
    "/report/telegram-published",
    status_code=201,
    summary="Report a Telegram publication event (poupi-baby callback)",
)
def report_telegram_published(
    payload: TelegramPublishReport,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Called by poupi-baby after each TelegramGroupProcessor execution.

    Stores the event in telegram_publication_events so the watchdog can
    determine last successful publication time without direct DB access.
    """
    from decimal import Decimal

    event = TelegramPublicationEvent(
        group_id=payload.group_id,
        product_id=payload.product_id,
        offer_id=payload.offer_id,
        marketplace=payload.marketplace,
        price=Decimal(str(payload.price)) if payload.price is not None else None,
        deal_score=payload.deal_score,
        status=payload.status,
        fail_reason=payload.fail_reason,
        published_at=datetime.now(tz=timezone.utc),
        reported_by=payload.reported_by,
    )
    db.add(event)
    db.commit()
    return {"status": "recorded", "event_id": event.id}


# ── GET /status ───────────────────────────────────────────────────────────────

@router.get("/status", summary="Current watchdog status (last run)")
def watchdog_status(db: Session = Depends(get_db)) -> dict[str, Any]:
    """Return the most recent WatchdogRun with check results."""
    run = (
        db.query(WatchdogRun)
        .order_by(WatchdogRun.run_at.desc())
        .first()
    )
    if not run:
        return {"status": "no_runs", "message": "No watchdog runs recorded yet."}

    return {
        "last_run_at": run.run_at.isoformat(),
        "overall_status": run.overall_status,
        "duration_ms": run.duration_ms,
        "alert_codes": run.alert_codes or [],
        "telegram_sent": run.telegram_sent,
        "check_results": run.check_results or {},
        "error_message": run.error_message,
    }


# ── GET /runs ─────────────────────────────────────────────────────────────────

@router.get("/runs", summary="Watchdog run history")
def watchdog_runs(
    hours: int = Query(24, ge=1, le=168),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Return recent WatchdogRun records."""
    since = datetime.now(tz=timezone.utc) - timedelta(hours=hours)
    runs = (
        db.query(WatchdogRun)
        .filter(WatchdogRun.run_at >= since)
        .order_by(WatchdogRun.run_at.desc())
        .limit(limit)
        .all()
    )
    return {
        "window_hours": hours,
        "total": len(runs),
        "runs": [
            {
                "id": r.id,
                "run_at": r.run_at.isoformat(),
                "overall_status": r.overall_status,
                "duration_ms": r.duration_ms,
                "alert_codes": r.alert_codes or [],
                "telegram_sent": r.telegram_sent,
            }
            for r in runs
        ],
    }


# ── GET /alerts ───────────────────────────────────────────────────────────────

@router.get("/alerts", summary="Aggregated alerts from the last watchdog run")
def watchdog_alerts(db: Session = Depends(get_db)) -> dict[str, Any]:
    """Return the alerts fired in the most recent watchdog run."""
    run = (
        db.query(WatchdogRun)
        .order_by(WatchdogRun.run_at.desc())
        .first()
    )
    if not run:
        return {"alerts": [], "run_at": None, "overall_status": "unknown"}

    all_alerts: list[dict] = []
    for check_name, check_data in (run.check_results or {}).items():
        for alert in check_data.get("alerts", []):
            all_alerts.append({**alert, "check": check_name})

    return {
        "run_at": run.run_at.isoformat(),
        "overall_status": run.overall_status,
        "alert_count": len(all_alerts),
        "alerts": all_alerts,
    }


# ── POST /heartbeat/send ──────────────────────────────────────────────────────

@router.post("/heartbeat/send", summary="Manually trigger a Telegram heartbeat")
def trigger_heartbeat(db: Session = Depends(get_db)) -> dict[str, Any]:
    """Manually trigger the Telegram heartbeat summary message."""
    from app.watchdog.service import WatchdogService

    svc = WatchdogService(db)
    sent = svc.heartbeat()
    return {"sent": sent, "triggered_at": datetime.now(tz=timezone.utc).isoformat()}


# ── GET /telegram-events ──────────────────────────────────────────────────────

@router.get("/telegram-events", summary="Recent Telegram publication events (from poupi-baby)")
def telegram_events(
    hours: int = Query(24, ge=1, le=168),
    status: str | None = Query(None, description="sent | failed | rate_limited | skipped"),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Return recent TelegramPublicationEvent records."""
    since = datetime.now(tz=timezone.utc) - timedelta(hours=hours)
    query = db.query(TelegramPublicationEvent).filter(
        TelegramPublicationEvent.published_at >= since
    )
    if status:
        query = query.filter(TelegramPublicationEvent.status == status)

    events = query.order_by(TelegramPublicationEvent.published_at.desc()).limit(limit).all()

    # Summary stats
    all_in_window = db.query(TelegramPublicationEvent).filter(
        TelegramPublicationEvent.published_at >= since
    ).all()
    by_status: dict[str, int] = {}
    for e in all_in_window:
        by_status[e.status] = by_status.get(e.status, 0) + 1

    return {
        "window_hours": hours,
        "total": len(all_in_window),
        "by_status": by_status,
        "events": [
            {
                "id": e.id,
                "marketplace": e.marketplace,
                "status": e.status,
                "price": float(e.price) if e.price else None,
                "deal_score": e.deal_score,
                "published_at": e.published_at.isoformat(),
                "fail_reason": e.fail_reason,
            }
            for e in events
        ],
    }
