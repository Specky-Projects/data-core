"""
NBA Quant — Telegram alerts (observation-only, no execution).

Sends signal notifications to TELEGRAM_CHAT_ID using TELEGRAM_BOT_TOKEN.
Currently scoped to BACK_TO_BACK_FADE_V1 signals only.

Observation-only: alerts describe the signal rationale and expected edge.
No execution logic, no position sizing, no real bets.

Environment variables:
  TELEGRAM_BOT_TOKEN : bot token from @BotFather
  TELEGRAM_CHAT_ID   : target chat / channel ID
  TELEGRAM_ENABLED   : "true" to enable sending (default: false)
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

import httpx

from app.modules.nba.quant.models import NbaFeatures, NbaGame, NbaSignal

logger = logging.getLogger(__name__)

_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
_ENABLED = os.environ.get("TELEGRAM_ENABLED", "false").lower() == "true"

_TELEGRAM_API = "https://api.telegram.org"
_SEND_TIMEOUT = 10.0

# Only alert for these setups
_ALERT_SETUPS = {"BACK_TO_BACK_FADE_V1"}


def _is_configured() -> tuple[bool, str]:
    """Check if Telegram is properly configured. Returns (ok, reason)."""
    if not _ENABLED:
        return False, "TELEGRAM_ENABLED != true"
    if not _BOT_TOKEN:
        return False, "TELEGRAM_BOT_TOKEN not set"
    if not _CHAT_ID:
        return False, "TELEGRAM_CHAT_ID not set"
    return True, ""


def format_b2b_alert(
    signal: NbaSignal,
    game: NbaGame,
    features: NbaFeatures | None = None,
) -> str:
    """
    Format a BACK_TO_BACK_FADE_V1 observation alert message.

    Returns Markdown-formatted text for Telegram.
    """
    game_dt = game.game_date
    if hasattr(game_dt, "strftime"):
        date_str = game_dt.strftime("%Y-%m-%d %H:%M UTC")
    else:
        date_str = str(game_dt)

    odd_str = (
        f"+{signal.odd:.0f}" if float(signal.odd) > 0 else f"{signal.odd:.0f}"
    )

    lines = [
        "🏀 *NBA Quant — Observation Alert*",
        "",
        "*Setup:* `BACK_TO_BACK_FADE_V1`",
        f"*Game:* {game.away_team} @ {game.home_team}",
        f"*Date:* {date_str}",
        "",
        f"*Signal:* Take {signal.selection} ML ({odd_str})",
        f"*Rationale:* {signal.rationale or 'Away team on back-to-back'}",
        f"*Confidence:* {float(signal.confidence):.0%}",
        "",
    ]

    if features:
        rest_diff = (
            (features.home_rest_days or 0) - (features.away_rest_days or 0)
        )
        lines += [
            "*Edge factors:*",
            (
                f"  • Home rest: {features.home_rest_days or '?'}d"
                f" vs away: {features.away_rest_days or '?'}d"
            ),
            f"  • Rest advantage: +{rest_diff}d",
        ]
        if features.home_last5_wins is not None and features.home_last5_games:
            lines.append(
                f"  • Home L5: {features.home_last5_wins}/{features.home_last5_games} wins"
            )
        if features.away_back_to_back:
            lines.append("  • Away on B2B ✓")
        lines.append("")

    lines += [
        "⚠️ _Observation only — no real bets._",
        f"_Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}_",
    ]

    return "\n".join(lines)


def send_alert(text: str) -> bool:
    """
    Send a Telegram message. Returns True on success, False on failure.
    Does not raise — all errors are logged.
    """
    ok, reason = _is_configured()
    if not ok:
        logger.debug("Telegram alert skipped: %s", reason)
        return False

    try:
        with httpx.Client(timeout=_SEND_TIMEOUT) as client:
            resp = client.post(
                f"{_TELEGRAM_API}/bot{_BOT_TOKEN}/sendMessage",
                json={
                    "chat_id": _CHAT_ID,
                    "text": text,
                    "parse_mode": "Markdown",
                    "disable_web_page_preview": True,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("ok"):
                logger.info("Telegram alert sent", extra={"chat_id": _CHAT_ID})
                return True
            logger.warning("Telegram API returned ok=false: %s", data)
            return False

    except httpx.HTTPStatusError as exc:
        logger.error(
            "Telegram send failed HTTP %s: %s",
            exc.response.status_code,
            exc.response.text[:200],
        )
        return False

    except Exception as exc:
        logger.error("Telegram send failed: %s", exc)
        return False


def send_signal_alert(
    signal: NbaSignal,
    game: NbaGame,
    features: NbaFeatures | None = None,
) -> bool:
    """
    Send an observation alert for a signal, if the setup is in _ALERT_SETUPS.
    Returns True if sent, False if skipped or failed.
    """
    if signal.setup_name not in _ALERT_SETUPS:
        return False

    text = format_b2b_alert(signal, game, features)
    return send_alert(text)


def validate_config() -> dict:
    """
    Validate Telegram configuration without sending a real message.
    Returns status dict for API health checks.
    """
    ok, reason = _is_configured()
    return {
        "configured": ok,
        "enabled": _ENABLED,
        "bot_token_set": bool(_BOT_TOKEN),
        "chat_id_set": bool(_CHAT_ID),
        "blocked_reason": reason if not ok else None,
        "alert_setups": list(_ALERT_SETUPS),
    }
