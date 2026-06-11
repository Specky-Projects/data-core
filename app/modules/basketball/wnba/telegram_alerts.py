"""
WNBA Quant — Telegram alerts via Alfredo (observation-only, no execution).

Guards:
  ENABLE_WNBA_TELEGRAM_SIMULATIONS=false  → all WNBA alerts suppressed (default)
  TELEGRAM_ENABLED=true                   → global Telegram on/off

Environment variables:
  TELEGRAM_BOT_TOKEN               : bot token from @BotFather
  EXECUTIVE_CHAT_ID                : Alfredo #executive channel
  TELEGRAM_CHAT_ID                 : fallback personal chat
  TELEGRAM_ENABLED                 : "true" to allow any send
  ENABLE_WNBA_TELEGRAM_SIMULATIONS : "true" to send WNBA signals (default false)
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

import httpx

from app.modules.basketball.wnba.models import WnbaFeatures, WnbaGame, WnbaQuantBet, WnbaSignal
from app.modules.basketball.shared.enums import BetStatus

logger = logging.getLogger(__name__)

_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
_CHAT_ID = (
    os.environ.get("EXECUTIVE_CHAT_ID", "")
    or os.environ.get("TELEGRAM_CHAT_ID", "")
)
_TELEGRAM_ENABLED = os.environ.get("TELEGRAM_ENABLED", "false").lower() == "true"
_WNBA_SIM_ENABLED = os.environ.get("ENABLE_WNBA_TELEGRAM_SIMULATIONS", "false").lower() == "true"

_TELEGRAM_API = "https://api.telegram.org"
_SEND_TIMEOUT = 10.0


def _is_configured() -> tuple[bool, str]:
    if not _TELEGRAM_ENABLED:
        return False, "TELEGRAM_ENABLED != true"
    if not _WNBA_SIM_ENABLED:
        return False, "ENABLE_WNBA_TELEGRAM_SIMULATIONS != true"
    if not _BOT_TOKEN:
        return False, "TELEGRAM_BOT_TOKEN not set"
    if not _CHAT_ID:
        return False, "EXECUTIVE_CHAT_ID (or TELEGRAM_CHAT_ID) not set"
    return True, ""


def _odd_str(odd: float) -> str:
    return f"+{odd:.0f}" if odd > 0 else f"{odd:.0f}"


def format_signal_alert(
    signal: WnbaSignal,
    game: WnbaGame,
    features: WnbaFeatures | None = None,
) -> str:
    game_dt = game.game_date
    date_str = game_dt.strftime("%Y-%m-%d %H:%M UTC") if hasattr(game_dt, "strftime") else str(game_dt)
    odd = float(signal.odd)

    lines = [
        "🏀 *WNBA Quant — Simulação*",
        "",
        f"*Setup:* `{signal.setup_name}`",
        f"*Jogo:* {game.away_team} @ {game.home_team}",
        f"*Data:* {date_str}",
        "",
        f"*Pick:* {signal.selection}",
        f"*Mercado:* {signal.market_type}",
    ]
    if signal.line is not None:
        lines.append(f"*Linha:* {float(signal.line):.1f}")
    lines += [
        f"*Odd:* {_odd_str(odd)}",
        f"*Stake:* 1u (paper)",
        "",
        f"*Racional:* {signal.rationale or '-'}",
        f"*Confiança:* {float(signal.confidence):.0%}",
        "",
    ]
    if features:
        lines += [
            "*Edge factors:*",
            f"  • Home rest: {features.home_rest_days or '?'}d vs Away: {features.away_rest_days or '?'}d",
        ]
        if features.away_back_to_back:
            lines.append("  • Away em B2B ✓")
        if features.home_back_to_back:
            lines.append("  • Home em B2B ⚠️")
        if features.home_last5_wins is not None and features.home_last5_games:
            lines.append(f"  • Home L5: {features.home_last5_wins}/{features.home_last5_games} wins")
        lines.append("")

    lines += [
        "⚠️ _Simulação apenas — sem aposta real._",
        f"_Gerado: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}_",
    ]
    return "\n".join(lines)


def format_settlement_alert(
    signal: WnbaSignal,
    bet: WnbaQuantBet,
    game: WnbaGame,
) -> str:
    odd = float(signal.odd)
    pnl_val = float(bet.pnl) if bet.pnl is not None else 0.0
    status_emoji = {"won": "✅", "lost": "❌", "void": "↩️", "pending": "⏳"}.get(
        bet.status.value, "❓"
    )
    pnl_str = f"+{pnl_val:.2f}u" if pnl_val >= 0 else f"{pnl_val:.2f}u"

    lines = [
        f"{status_emoji} *WNBA Quant — Resultado*",
        "",
        f"*Setup:* `{signal.setup_name}`",
        f"*Jogo:* {game.away_team} @ {game.home_team}",
        f"*Pick:* {signal.selection} @ {_odd_str(odd)}",
        "",
        f"*Resultado:* `{bet.status.value.upper()}`",
        f"*PnL:* `{pnl_str}`",
        f"*Placar:* {game.home_score or '?'}-{game.away_score or '?'} ({game.home_team} casa)",
        "",
        f"_Fechado: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}_",
    ]
    return "\n".join(lines)


def send_alert(text: str) -> bool:
    ok, reason = _is_configured()
    if not ok:
        logger.debug("WNBA Telegram skipped: %s", reason)
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
                logger.info("WNBA Telegram alert sent")
                return True
            logger.warning("Telegram API ok=false: %s", data)
            return False
    except Exception as exc:
        logger.error("WNBA Telegram send failed: %s", exc)
        return False


def send_signal_alert(
    signal: WnbaSignal,
    game: WnbaGame,
    features: WnbaFeatures | None = None,
    *,
    db=None,
) -> bool:
    if signal.telegram_sent_at is not None:
        return False

    text = format_signal_alert(signal, game, features)
    sent = send_alert(text)

    if sent and db is not None:
        signal.telegram_sent_at = datetime.now(timezone.utc)
        db.add(signal)
        db.commit()

    return sent


def send_settlement_alert(
    signal: WnbaSignal,
    bet: WnbaQuantBet,
    game: WnbaGame,
    *,
    db=None,
) -> bool:
    if bet.status == BetStatus.pending:
        return False
    if bet.settlement_telegram_sent_at is not None:
        return False

    text = format_settlement_alert(signal, bet, game)
    sent = send_alert(text)

    if sent and db is not None:
        bet.settlement_telegram_sent_at = datetime.now(timezone.utc)
        db.add(bet)
        db.commit()

    return sent


def validate_config() -> dict:
    ok, reason = _is_configured()
    return {
        "configured": ok,
        "telegram_enabled": _TELEGRAM_ENABLED,
        "wnba_simulations_enabled": _WNBA_SIM_ENABLED,
        "bot_token_set": bool(_BOT_TOKEN),
        "chat_id_set": bool(_CHAT_ID),
        "blocked_reason": reason if not ok else None,
    }
