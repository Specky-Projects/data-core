"""Text reports from structured storage analytics."""

from __future__ import annotations

from domains.crypto_coin.analytics.storage_analysis import storage_overview
from domains.crypto_coin.data.storage.repository import StorageRepository


def build_storage_report(
    storage: StorageRepository,
    *,
    symbol: str,
    timeframe: str,
    strategy_id: str = "trend_following",
) -> str:
    overview = storage_overview(
        storage,
        symbol=symbol,
        timeframe=timeframe,
        strategy_id=strategy_id,
        recent_limit=200,
    )
    summary = overview.get("summary") or {}
    signals = overview.get("signal_decisions") or {}
    calibration = overview.get("calibration") or {}
    advisory = overview.get("advisory") or {}
    regimes = overview.get("regime_performance") or []

    lines = [
        f"Storage report - {symbol} {timeframe}",
        "",
        f"Equity atual: {_money(summary.get('latest_equity'))}",
        f"P&L recente: {_money(summary.get('recent_net_pnl'))}",
        f"Win rate recente: {_pct(summary.get('recent_win_rate'))}",
        f"Drawdown max.: {_pct(summary.get('max_drawdown'))}",
        "",
        "Sinais:",
        f"- aceitos: {signals.get('accepted_decisions', 0)}",
        f"- rejeitados: {signals.get('rejected_decisions', 0)}",
        f"- taxa aceitacao: {_pct(signals.get('acceptance_rate'))}",
        "",
        "Calibracao:",
        f"- stop sugerido: {_pct(calibration.get('suggested_stop_loss_pct'))}",
        f"- take sugerido: {_pct(calibration.get('suggested_take_profit_pct'))}",
        "",
        "Regimes:",
    ]
    if regimes:
        for row in regimes[:5]:
            lines.append(
                f"- {row.get('regime')}: trades={row.get('total_trades')} "
                f"win={_pct(row.get('win_rate'))} pnl={_money(row.get('net_pnl'))}"
            )
    else:
        lines.append("- sem dados")

    recs = advisory.get("recommendations") or []
    lines.extend(["", "Advisory:"])
    if recs:
        for rec in recs[:5]:
            lines.append(f"- [{rec.get('severity')}] {rec.get('message')}")
    else:
        lines.append("- sem recomendacoes")

    return "\n".join(lines)


def _money(value) -> str:
    if value is None:
        return "-"
    return f"{float(value):+.2f}"


def _pct(value) -> str:
    if value is None:
        return "-"
    return f"{float(value):.2f}%"
