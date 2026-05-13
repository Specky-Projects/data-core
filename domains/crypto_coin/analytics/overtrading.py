"""Optional overtrading guardrails derived from stored trades."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from domains.crypto_coin.data.storage.repository import StorageRepository


@dataclass(frozen=True)
class OvertradingDecision:
    allow_entry: bool
    reason: str = ""


def overtrading_decision(
    storage: StorageRepository,
    *,
    symbol: str,
    strategy_id: str,
    now: datetime,
    max_trades_per_day: int = 0,
    cooldown_after_loss_minutes: int = 0,
    max_consecutive_losses: int = 0,
) -> OvertradingDecision:
    trades = storage.fetch_recent_trades(limit=200, symbol=symbol, strategy_id=strategy_id)
    closed = [trade for trade in trades if trade.get("pnl") is not None]

    if max_trades_per_day > 0:
        today = now.date().isoformat()
        trades_today = [trade for trade in closed if str(trade.get("timestamp", "")).startswith(today)]
        if len(trades_today) >= max_trades_per_day:
            return OvertradingDecision(False, f"max_trades_per_day:{max_trades_per_day}")

    if cooldown_after_loss_minutes > 0 and closed:
        last = closed[0]
        if (last.get("pnl") or 0) < 0:
            last_ts = _parse_datetime(last.get("timestamp"))
            if last_ts and now - last_ts < timedelta(minutes=cooldown_after_loss_minutes):
                return OvertradingDecision(False, f"cooldown_after_loss:{cooldown_after_loss_minutes}m")

    if max_consecutive_losses > 0:
        streak = 0
        for trade in closed:
            if (trade.get("pnl") or 0) < 0:
                streak += 1
                if streak >= max_consecutive_losses:
                    return OvertradingDecision(False, f"max_consecutive_losses:{max_consecutive_losses}")
            else:
                break

    return OvertradingDecision(True)


def _parse_datetime(value) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None
