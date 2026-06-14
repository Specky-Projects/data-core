"""Analytics built from the structured storage layer."""

from __future__ import annotations

from domains.crypto_coin.analytics.ai_decision import build_ai_decision
from domains.crypto_coin.analytics.decision_support import advisory_report, calibration_report
from domains.crypto_coin.analytics.metrics.calc import max_drawdown, profit_factor, sharpe_ratio
from domains.crypto_coin.analytics.shadow_compare import shadow_paper_comparison
from domains.crypto_coin.backtesting.storage_replay import replay_current_strategy
from domains.crypto_coin.data.storage.repository import StorageRepository


def storage_overview(
    storage: StorageRepository,
    *,
    symbol: str | None = None,
    timeframe: str | None = None,
    strategy_id: str | None = None,
    recent_limit: int = 20,
    replay_start: str | None = None,
    replay_end: str | None = None,
) -> dict:
    """Return a compact operational snapshot from persisted bot memory."""
    recent_trades = storage.fetch_recent_trades(
        limit=recent_limit,
        symbol=symbol,
        strategy_id=strategy_id,
    )
    equity_curve = storage.fetch_equity_curve(
        symbol=symbol,
        timeframe=timeframe,
    )
    regime_performance = storage.fetch_regime_performance(
        symbol=symbol,
        timeframe=timeframe,
    )
    mae_mfe = storage.fetch_mae_mfe_stats(
        symbol=symbol,
        strategy_id=strategy_id,
    )
    confidence_performance = storage.fetch_confidence_performance(
        symbol=symbol,
        strategy_id=strategy_id,
    )
    signal_decisions = storage.fetch_signal_decision_summary(
        symbol=symbol,
        timeframe=timeframe,
    )
    strategy_versions = storage.fetch_strategy_version_performance(
        symbol=symbol,
        strategy_id=strategy_id,
    )
    strategy_regimes = storage.fetch_strategy_version_regime_performance(
        symbol=symbol,
        timeframe=timeframe,
        strategy_id=strategy_id,
    )
    shadow_summary = storage.fetch_shadow_summary(
        symbol=symbol,
        timeframe=timeframe,
    )
    shadow_compare = {}
    if symbol:
        shadow_compare = shadow_paper_comparison(
            storage,
            symbol=symbol,
            timeframe=timeframe,
            strategy_id=strategy_id or "trend_following",
        )
    replay = {}
    if symbol and timeframe:
        replay = replay_current_strategy(
            storage,
            symbol=symbol,
            timeframe=timeframe,
            strategy_version="current",
            limit=1_000,
            start=replay_start,
            end=replay_end,
        )
    ai_decision = build_ai_decision(
        replay=replay,
        confidence_performance=confidence_performance,
        regimes=regime_performance,
        shadow=shadow_summary,
        strategy_regimes=strategy_regimes,
    )
    health = storage.fetch_health()

    closed_trades = [trade for trade in recent_trades if trade.get("pnl") is not None]
    equity_values = [point["equity"] for point in equity_curve if point.get("equity") is not None]
    pnl_values = [trade["pnl"] for trade in closed_trades if trade.get("pnl") is not None]
    pnl_pcts = [trade["pnl_pct"] for trade in closed_trades if trade.get("pnl_pct") is not None]

    total_trades = len(closed_trades)
    wins = len([pnl for pnl in pnl_values if pnl > 0])

    return {
        "summary": {
            "total_recent_closed_trades": total_trades,
            "recent_win_rate": round((wins / total_trades) * 100, 2) if total_trades else 0.0,
            "recent_net_pnl": round(sum(pnl_values), 8) if pnl_values else 0.0,
            "recent_profit_factor": profit_factor(pnl_values),
            "recent_sharpe": sharpe_ratio(pnl_pcts),
            "max_drawdown": max_drawdown(equity_values),
            "latest_equity": equity_values[-1] if equity_values else None,
        },
        "mae_mfe": mae_mfe,
        "calibration": calibration_report(
            storage,
            symbol=symbol,
            strategy_id=strategy_id or "trend_following",
        ),
        "confidence_performance": confidence_performance,
        "signal_decisions": signal_decisions,
        "strategy_versions": strategy_versions,
        "strategy_regimes": strategy_regimes,
        "shadow": shadow_summary,
        "shadow_compare": shadow_compare,
        "replay": replay,
        "ai_decision": ai_decision,
        "health": health,
        "advisory": advisory_report(
            storage,
            symbol=symbol,
            timeframe=timeframe or "",
            strategy_id=strategy_id or "trend_following",
        ),
        "regime_performance": regime_performance,
        "recent_trades": recent_trades,
        "equity_curve": equity_curve,
    }


def weak_regimes(
    storage: StorageRepository,
    *,
    symbol: str | None = None,
    timeframe: str | None = None,
    min_trades: int = 5,
) -> list[dict]:
    """Regimes with enough data and negative net performance."""
    regimes = storage.fetch_regime_performance(symbol=symbol, timeframe=timeframe)
    return [
        regime
        for regime in regimes
        if (regime.get("total_trades") or 0) >= min_trades
        and (regime.get("net_pnl") or 0) < 0
    ]


def stop_take_profit_hints(storage: StorageRepository, *, symbol: str | None = None) -> dict:
    """Return rough stop/take-profit hints from historical MAE/MFE."""
    stats = storage.fetch_mae_mfe_stats(symbol=symbol)
    return {
        "avg_mae": stats.get("avg_mae"),
        "worst_mae": stats.get("worst_mae"),
        "avg_mfe": stats.get("avg_mfe"),
        "best_mfe": stats.get("best_mfe"),
        "note": "Use as diagnostic input, not as an automatic parameter change.",
    }
