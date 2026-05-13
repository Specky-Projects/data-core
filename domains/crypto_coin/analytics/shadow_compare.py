"""Compare shadow-live theoretical trades with paper/live closed trades."""

from __future__ import annotations

from datetime import datetime, timedelta

from domains.crypto_coin.data.storage.repository import StorageRepository


def shadow_paper_comparison(
    storage: StorageRepository,
    *,
    symbol: str,
    timeframe: str | None = None,
    strategy_id: str = "trend_following",
    max_minutes: int = 60,
) -> dict:
    shadow = [
        row for row in storage.fetch_shadow_trades(symbol=symbol, timeframe=timeframe, limit=500)
        if row.get("status") == "closed" and row.get("pnl_pct") is not None
    ]
    trades = [
        row for row in storage.fetch_recent_trades(limit=500, symbol=symbol, strategy_id=strategy_id)
        if row.get("pnl_pct") is not None
    ]
    if not shadow or not trades:
        return {"pairs": 0, "avg_delta_pct": None, "items": []}

    pairs = []
    used = set()
    for srow in shadow:
        entry_ts = _parse_ts(srow.get("entry_timestamp"))
        if not entry_ts:
            continue
        match = None
        match_idx = None
        best_delta = None
        for idx, trade in enumerate(trades):
            if idx in used:
                continue
            trade_ts = _parse_ts(trade.get("timestamp"))
            if not trade_ts:
                continue
            delta = abs((trade_ts - entry_ts).total_seconds()) / 60
            if delta <= max_minutes and (best_delta is None or delta < best_delta):
                match = trade
                match_idx = idx
                best_delta = delta
        if match is None or match_idx is None:
            continue
        used.add(match_idx)
        shadow_pct = float(srow.get("pnl_pct") or 0)
        paper_pct = float(match.get("pnl_pct") or 0)
        pairs.append({
            "shadow_id": srow.get("id"),
            "trade_id": match.get("id"),
            "timestamp": srow.get("entry_timestamp"),
            "shadow_pnl_pct": shadow_pct,
            "paper_pnl_pct": paper_pct,
            "delta_pct": round(shadow_pct - paper_pct, 4),
            "minutes_delta": round(best_delta or 0, 2),
        })

    deltas = [item["delta_pct"] for item in pairs]
    return {
        "pairs": len(pairs),
        "avg_delta_pct": round(sum(deltas) / len(deltas), 4) if deltas else None,
        "shadow_better": len([item for item in pairs if item["delta_pct"] > 0]),
        "paper_better": len([item for item in pairs if item["delta_pct"] < 0]),
        "items": pairs[-20:],
    }


def _parse_ts(value) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None
