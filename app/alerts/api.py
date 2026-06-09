"""Phase 11 alert routing endpoints + Phase 12 Telegram config/status."""
from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from api.deps import db_session
from app.alerts.channel import CHANNEL_ENV, AlertChannel
from app.alerts.router import TelegramRouter

router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])
telegram_router = APIRouter(prefix="/api/v1/telegram", tags=["telegram"])


@router.get("/routes")
def get_routes() -> dict[str, Any]:
    """Return full routing table: alert_type → channel, rate limits, env config.

    Shows which chat_id env vars are configured and which are missing.
    """
    return TelegramRouter.routing_table()


@router.post("/test")
def send_test_alert(
    db: Session = Depends(db_session),  # noqa: B008
    channel: AlertChannel = Query(  # noqa: B008
        default=AlertChannel.OPERATIONAL,
        description="Channel to test: BUSINESS | OPERATIONAL | EXECUTIVE | CRITICAL",
    ),
) -> dict[str, Any]:
    """Send a test message to the specified channel.

    Useful for verifying env vars (BUSINESS_CHAT_ID, OPERATIONAL_CHAT_ID, etc.)
    are correctly set and the bot can reach each channel.

    Note: counts toward the channel's rate limit (max per hour applies).
    Does NOT apply dedup — each call sends if rate limit allows.
    """
    router_obj = TelegramRouter()
    result = router_obj.send_test(channel, db=db)
    result["note"] = (
        "sent=false with reason=telegram_disabled means TELEGRAM_ENABLED or "
        "TELEGRAM_BOT_TOKEN is not set. "
        f"reason=no_chat_id means {channel.value}_CHAT_ID env var is missing."
    )
    return result


# ---------------------------------------------------------------------------
# Phase 12 — /api/v1/telegram/config
# ---------------------------------------------------------------------------


@telegram_router.get("/config")
def telegram_config() -> dict[str, Any]:
    """Return Telegram configuration status.

    Reports which env vars are configured.
    Never exposes token values — only whether they are set.
    """
    token_set = bool(os.getenv("TELEGRAM_BOT_TOKEN", ""))
    enabled = os.getenv("TELEGRAM_ENABLED", "false").lower() in ("1", "true", "yes")

    # Legacy fallback vars
    legacy_chat_id_set = bool(os.getenv("TELEGRAM_CHAT_ID", ""))
    system_chat_id_set = bool(os.getenv("TELEGRAM_SYSTEM_CHAT_ID", ""))

    # Channel-specific vars
    channels: dict[str, Any] = {}
    for channel in AlertChannel:
        env_var = CHANNEL_ENV[channel]
        val = os.getenv(env_var, "")
        channels[channel.value] = {
            "env_var": env_var,
            "configured": bool(val),
            "effective_chat_id_configured": bool(val)
            or legacy_chat_id_set
            or system_chat_id_set,
        }

    any_channel_configured = any(
        bool(os.getenv(CHANNEL_ENV[c], "")) for c in AlertChannel
    )

    warnings: list[str] = []
    if not token_set:
        warnings.append("TELEGRAM_BOT_TOKEN is not set — no messages will be sent")
    if not enabled:
        warnings.append("TELEGRAM_ENABLED != true — sending is disabled")
    for ch in AlertChannel:
        env_var = CHANNEL_ENV[ch]
        if not os.getenv(env_var, ""):
            warnings.append(
                f"{env_var} not set — {ch.value} channel will fall back to "
                "TELEGRAM_CHAT_ID (if set)"
            )

    return {
        "bot_configured": token_set,
        "enabled": enabled,
        "token_env_var": "TELEGRAM_BOT_TOKEN",
        "token_set": token_set,
        "legacy_chat_id_set": legacy_chat_id_set,
        "system_chat_id_set": system_chat_id_set,
        "any_channel_configured": any_channel_configured,
        "channels": channels,
        "warnings": warnings,
        "note": (
            "Token values are never returned. "
            "Use POST /api/v1/alerts/test?channel=<CHANNEL> to verify delivery."
        ),
    }
