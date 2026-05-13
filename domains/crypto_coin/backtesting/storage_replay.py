"""Replay utilities for market snapshots persisted in storage."""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

from domains.crypto_coin.data.storage.repository import StorageRepository
from domains.crypto_coin.indicators.technical import Indicators, MarketRegime
from domains.crypto_coin.strategies.trend_following.strategy import Signal, get_signal
from domains.crypto_coin.analytics.metrics.calc import max_drawdown, profit_factor, sharpe_ratio


@dataclass(frozen=True)
class ReplayFrame:
    timestamp: str
    symbol: str
    timeframe: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    indicators: dict


def load_replay_frames(
    storage: StorageRepository,
    *,
    symbol: str | None = None,
    timeframe: str | None = None,
    limit: int | None = None,
) -> list[ReplayFrame]:
    """Load stored market snapshots in chronological order for replay/backtests."""
    rows = storage.fetch_market_snapshots(symbol=symbol, timeframe=timeframe, limit=limit)
    return [
        ReplayFrame(
            timestamp=row["timestamp"],
            symbol=row["symbol"],
            timeframe=row["timeframe"],
            open=float(row["open"]),
            high=float(row["high"]),
            low=float(row["low"]),
            close=float(row["close"]),
            volume=float(row["volume"]),
            indicators=row.get("indicators") or {},
        )
        for row in rows
    ]


def replay_summary(frames: list[ReplayFrame]) -> dict:
    if not frames:
        return {"frames": 0}
    first = frames[0]
    last = frames[-1]
    ret = ((last.close - first.close) / first.close * 100) if first.close else 0.0
    return {
        "frames": len(frames),
        "symbol": last.symbol,
        "timeframe": last.timeframe,
        "start": first.timestamp,
        "end": last.timestamp,
        "first_close": first.close,
        "last_close": last.close,
        "buy_and_hold_pct": round(ret, 4),
    }


def filter_replay_summary(storage: StorageRepository, *, symbol: str, timeframe: str) -> dict:
    """Summarize current filter behavior from persisted signal decisions."""
    signals = storage.fetch_signal_decision_summary(symbol=symbol, timeframe=timeframe)
    reasons = signals.get("by_reason") or []
    blocked = [
        row for row in reasons
        if not row.get("accepted") and str(row.get("reason", "")).startswith("blocked")
    ]
    return {
        "total_decisions": signals.get("total_decisions", 0),
        "accepted_decisions": signals.get("accepted_decisions", 0),
        "rejected_decisions": signals.get("rejected_decisions", 0),
        "acceptance_rate": signals.get("acceptance_rate", 0.0),
        "blocked_reasons": blocked,
        "note": "Replay de outcome dos bloqueios exige precificacao futura por decisao.",
    }


def replay_current_strategy(
    storage: StorageRepository,
    *,
    symbol: str,
    timeframe: str,
    strategy_version: str = "current",
    stop_loss_pct: float = 3.0,
    take_profit_pct: float = 6.0,
    initial_balance: float = 10_000.0,
    limit: int = 1_000,
    start: str | None = None,
    end: str | None = None,
) -> dict:
    """Replay stored candles with the current strategy and compare saved decisions."""
    frames = load_replay_frames(storage, symbol=symbol, timeframe=timeframe, limit=limit)
    frames = _filter_frames(frames, start=start, end=end)
    if len(frames) < 2:
        return {"ready": False, "reason": "snapshots insuficientes", "frames": len(frames)}

    old_decisions = _decision_index(
        storage.fetch_signal_decisions(symbol=symbol, timeframe=timeframe, limit=limit * 2)
    )
    cfg = SimpleNamespace(stop_loss_pct=stop_loss_pct, take_profit_pct=take_profit_pct)

    in_position = False
    buy_price = None
    entry_regime = None
    equity = initial_balance
    equity_curve = [equity]
    trades: list[dict] = []
    comparisons: list[dict] = []
    strategy_return_pct = 0.0

    for frame in frames:
        ind = _indicators_from_frame(frame)
        old = old_decisions.get(frame.timestamp)
        signal = get_signal(ind, in_position, buy_price, cfg, strategy_return_pct)
        new_accepted = signal in (
            Signal.BUY,
            Signal.RANGE_BUY,
            Signal.SELL,
            Signal.RANGE_SELL,
            Signal.STOP_LOSS,
            Signal.TAKE_PROFIT,
        )

        if old:
            comparisons.append({
                "timestamp": frame.timestamp,
                "old_signal": old.get("signal"),
                "old_accepted": bool(old.get("accepted")),
                "old_reason": old.get("reason"),
                "new_signal": signal.value,
                "new_accepted": new_accepted,
                "regime": ind.regime.value,
            })

        if not in_position and signal in (Signal.BUY, Signal.RANGE_BUY):
            in_position = True
            buy_price = frame.close
            entry_regime = ind.regime.value
            continue

        if in_position and buy_price:
            exit_signal = signal
            exit_price = frame.close
            if frame.low <= buy_price * (1 - stop_loss_pct / 100):
                exit_signal = Signal.STOP_LOSS
                exit_price = buy_price * (1 - stop_loss_pct / 100)
            elif frame.high >= buy_price * (1 + take_profit_pct / 100):
                exit_signal = Signal.TAKE_PROFIT
                exit_price = buy_price * (1 + take_profit_pct / 100)

            if exit_signal in (Signal.SELL, Signal.RANGE_SELL, Signal.STOP_LOSS, Signal.TAKE_PROFIT):
                pnl_pct = (exit_price - buy_price) / buy_price * 100
                pnl = equity * (pnl_pct / 100)
                equity += pnl
                strategy_return_pct = (equity - initial_balance) / initial_balance * 100
                equity_curve.append(equity)
                trades.append({
                    "entry_price": buy_price,
                    "exit_price": exit_price,
                    "exit_signal": exit_signal.value,
                    "pnl": pnl,
                    "pnl_pct": pnl_pct,
                    "regime": entry_regime,
                })
                in_position = False
                buy_price = None
                entry_regime = None

    pnl_values = [trade["pnl"] for trade in trades]
    pnl_pcts = [trade["pnl_pct"] for trade in trades]
    wins = len([pnl for pnl in pnl_values if pnl > 0])
    signal_changes = len([
        item for item in comparisons
        if item["old_signal"] != item["new_signal"]
    ])
    acceptance_changes = len([
        item for item in comparisons
        if item["old_accepted"] != item["new_accepted"]
    ])

    return {
        "ready": True,
        "strategy_version": strategy_version,
        "frames": len(frames),
        "start": frames[0].timestamp,
        "end": frames[-1].timestamp,
        "trades": len(trades),
        "wins": wins,
        "losses": len(trades) - wins,
        "win_rate": round(wins / len(trades) * 100, 2) if trades else 0.0,
        "net_pnl": round(sum(pnl_values), 8) if pnl_values else 0.0,
        "net_pnl_pct": round((equity - initial_balance) / initial_balance * 100, 4),
        "profit_factor": profit_factor(pnl_values),
        "sharpe": sharpe_ratio(pnl_pcts),
        "max_drawdown": max_drawdown(equity_curve),
        "signal_comparisons": len(comparisons),
        "signal_changes": signal_changes,
        "acceptance_changes": acceptance_changes,
        "change_rate": round(signal_changes / len(comparisons) * 100, 2) if comparisons else 0.0,
        "acceptance_change_rate": round(acceptance_changes / len(comparisons) * 100, 2) if comparisons else 0.0,
        "performance_by_regime": _performance_by_regime(trades),
        "blocked_outcomes": blocked_signal_outcomes(
            storage,
            symbol=symbol,
            timeframe=timeframe,
            frames=frames,
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=take_profit_pct,
        ),
        "recent_changes": [
            item for item in comparisons[-20:]
            if item["old_signal"] != item["new_signal"]
            or item["old_accepted"] != item["new_accepted"]
        ][-8:],
    }


def blocked_signal_outcomes(
    storage: StorageRepository,
    *,
    symbol: str,
    timeframe: str,
    frames: list[ReplayFrame] | None = None,
    stop_loss_pct: float = 3.0,
    take_profit_pct: float = 6.0,
    horizon_candles: int = 12,
) -> dict:
    """Price blocked entry decisions against future candles."""
    frames = frames or load_replay_frames(storage, symbol=symbol, timeframe=timeframe)
    if len(frames) < 2:
        return {"total": 0, "by_reason": []}
    frame_by_ts = {frame.timestamp: idx for idx, frame in enumerate(frames)}
    decisions = storage.fetch_signal_decisions(symbol=symbol, timeframe=timeframe)
    blocked = [
        row for row in decisions
        if not row.get("accepted")
        and str(row.get("reason", "")).startswith("blocked")
        and row.get("timestamp") in frame_by_ts
    ]
    grouped: dict[str, list[float]] = {}
    unresolved = 0
    for row in blocked:
        idx = frame_by_ts[str(row["timestamp"])]
        entry = float(row.get("price") or frames[idx].close)
        if entry <= 0:
            continue
        outcome = _future_outcome(
            frames[idx + 1: idx + 1 + horizon_candles],
            entry=entry,
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=take_profit_pct,
        )
        if outcome is None:
            unresolved += 1
            continue
        grouped.setdefault(str(row.get("reason") or "blocked"), []).append(outcome)
    by_reason = []
    for reason, pnl_pcts in grouped.items():
        wins = len([value for value in pnl_pcts if value > 0])
        by_reason.append({
            "reason": reason,
            "count": len(pnl_pcts),
            "wins": wins,
            "losses": len(pnl_pcts) - wins,
            "win_rate": round(wins / len(pnl_pcts) * 100, 2) if pnl_pcts else 0.0,
            "avg_pnl_pct": round(sum(pnl_pcts) / len(pnl_pcts), 4) if pnl_pcts else 0.0,
            "net_pnl_pct": round(sum(pnl_pcts), 4),
        })
    return {
        "total": sum(item["count"] for item in by_reason),
        "unresolved": unresolved,
        "horizon_candles": horizon_candles,
        "by_reason": sorted(by_reason, key=lambda item: item["net_pnl_pct"], reverse=True),
    }


def _decision_index(rows: list[dict]) -> dict[str, dict]:
    out = {}
    for row in rows:
        timestamp = row.get("timestamp")
        if timestamp:
            out[str(timestamp)] = row
    return out


def _filter_frames(
    frames: list[ReplayFrame],
    *,
    start: str | None = None,
    end: str | None = None,
) -> list[ReplayFrame]:
    if start:
        frames = [frame for frame in frames if frame.timestamp >= start]
    if end:
        frames = [frame for frame in frames if frame.timestamp <= end]
    return frames


def _future_outcome(
    future: list[ReplayFrame],
    *,
    entry: float,
    stop_loss_pct: float,
    take_profit_pct: float,
) -> float | None:
    if not future:
        return None
    stop = entry * (1 - stop_loss_pct / 100)
    take = entry * (1 + take_profit_pct / 100)
    for frame in future:
        if frame.low <= stop:
            return (stop - entry) / entry * 100
        if frame.high >= take:
            return (take - entry) / entry * 100
    return (future[-1].close - entry) / entry * 100


def _indicators_from_frame(frame: ReplayFrame) -> Indicators:
    data = frame.indicators or {}
    regime = _regime_from_value(data.get("regime"))
    return Indicators(
        close=frame.close,
        ma_fast=data.get("ma_fast"),
        ma_slow=data.get("ma_slow"),
        rsi=data.get("rsi"),
        bb_upper=data.get("bb_upper"),
        bb_mid=data.get("bb_mid"),
        bb_lower=data.get("bb_lower"),
        bb_width=data.get("bb_width"),
        volume_ratio=data.get("volume_ratio"),
        volume_confirm=bool(data.get("volume_confirm", False)),
        volume_trend=data.get("volume_trend") or "neutral",
        adx=data.get("adx"),
        atr=data.get("atr"),
        atr_pct=data.get("atr_pct"),
        atr_momentum=data.get("atr_momentum"),
        vwap=data.get("vwap"),
        price_above_vwap=bool(data.get("price_above_vwap", False)),
        hv=data.get("hv"),
        breakout_score=float(data.get("breakout_score") or 0.0),
        regime=regime,
        buy_and_hold_pct=data.get("buy_and_hold_pct"),
        confidence=int(data.get("confidence") or 0),
        ma_cross_bull=bool(data.get("ma_cross_bull", False)),
        ma_cross_bear=bool(data.get("ma_cross_bear", False)),
        rsi_oversold=bool(data.get("rsi_oversold", False)),
        rsi_overbought=bool(data.get("rsi_overbought", False)),
        price_below_bb=bool(data.get("price_below_bb", False)),
        price_above_bb=bool(data.get("price_above_bb", False)),
    )


def _regime_from_value(value) -> MarketRegime:
    for regime in MarketRegime:
        if value == regime.value or value == regime.name:
            return regime
    text = str(value or "").lower()
    if "alta" in text:
        return MarketRegime.TRENDING_UP
    if "baixa" in text:
        return MarketRegime.TRENDING_DOWN
    if "lateral" in text:
        return MarketRegime.RANGING
    return MarketRegime.UNKNOWN


def _performance_by_regime(trades: list[dict]) -> list[dict]:
    grouped: dict[str, list[dict]] = {}
    for trade in trades:
        grouped.setdefault(trade.get("regime") or "unknown", []).append(trade)
    out = []
    for regime, items in grouped.items():
        pnl = [item["pnl"] for item in items]
        wins = len([value for value in pnl if value > 0])
        out.append({
            "regime": regime,
            "trades": len(items),
            "win_rate": round(wins / len(items) * 100, 2) if items else 0.0,
            "net_pnl": round(sum(pnl), 8),
            "avg_pnl_pct": round(sum(item["pnl_pct"] for item in items) / len(items), 4),
        })
    return sorted(out, key=lambda item: item["net_pnl"], reverse=True)
