"""Decision support derived from storage analytics."""

from __future__ import annotations

from dataclasses import dataclass

from domains.crypto_coin.data.storage.repository import StorageRepository


@dataclass(frozen=True)
class RegimeDecision:
    allow_entry: bool
    reason: str = ""
    confidence_adjustment: int = 0


def regime_entry_decision(
    storage: StorageRepository,
    *,
    symbol: str,
    timeframe: str,
    regime: str,
    min_trades: int = 6,
    min_win_rate: float = 40.0,
    max_negative_pnl: float = 0.0,
) -> RegimeDecision:
    """Block or penalize entries in regimes that have proven weak."""
    regimes = storage.fetch_regime_performance(symbol=symbol, timeframe=timeframe)
    current = next((row for row in regimes if row.get("regime") == regime), None)
    if not current:
        return RegimeDecision(True)

    total = current.get("total_trades") or 0
    if total < min_trades:
        return RegimeDecision(True)

    net_pnl = current.get("net_pnl") or 0.0
    win_rate = current.get("win_rate") or 0.0

    if net_pnl < max_negative_pnl and win_rate < min_win_rate:
        return RegimeDecision(
            False,
            (
                f"regime historicamente fraco: {regime} | "
                f"trades={total} | win_rate={win_rate:.1f}% | pnl={net_pnl:.2f}"
            ),
        )

    if net_pnl < max_negative_pnl:
        return RegimeDecision(
            True,
            f"regime com P&L negativo; exigindo mais confianca: {regime}",
            confidence_adjustment=10,
        )

    return RegimeDecision(True)


def calibration_report(
    storage: StorageRepository,
    *,
    symbol: str,
    strategy_id: str = "trend_following",
) -> dict:
    """Suggest conservative stop/take diagnostics from historical MAE/MFE."""
    stats = storage.fetch_mae_mfe_stats(symbol=symbol, strategy_id=strategy_id)
    total = stats.get("total_trades") or 0
    if total <= 0:
        return {"ready": False, "reason": "sem trades fechados suficientes"}

    avg_mae = stats.get("avg_mae")
    avg_mfe = stats.get("avg_mfe")
    worst_mae = stats.get("worst_mae")
    best_mfe = stats.get("best_mfe")

    suggested_stop = None
    if avg_mae is not None:
        suggested_stop = round(min(abs(avg_mae) * 1.5, abs(worst_mae or avg_mae)), 2)

    suggested_take_profit = None
    if avg_mfe is not None:
        cap = abs(best_mfe or avg_mfe)
        suggested_take_profit = round(min(abs(avg_mfe) * 0.8, cap), 2)

    return {
        "ready": total >= 6,
        "total_trades": total,
        "avg_mae": avg_mae,
        "worst_mae": worst_mae,
        "avg_mfe": avg_mfe,
        "best_mfe": best_mfe,
        "suggested_stop_loss_pct": suggested_stop,
        "suggested_take_profit_pct": suggested_take_profit,
        "note": "diagnostico conservador; nao altera parametros automaticamente",
    }


def advisory_report(
    storage: StorageRepository,
    *,
    symbol: str,
    timeframe: str,
    strategy_id: str = "trend_following",
) -> dict:
    """Human-review recommendations. Nothing here changes bot parameters."""
    regimes = storage.fetch_regime_performance(symbol=symbol, timeframe=timeframe)
    confidence = storage.fetch_confidence_performance(symbol=symbol, strategy_id=strategy_id)
    calibration = calibration_report(storage, symbol=symbol, strategy_id=strategy_id)

    weak = [
        row for row in regimes
        if (row.get("total_trades") or 0) >= 6 and (row.get("net_pnl") or 0) < 0
    ]
    best_confidence = None
    if confidence:
        best_confidence = max(confidence, key=lambda row: row.get("net_pnl") or 0)

    recommendations = []
    for row in weak:
        recommendations.append({
            "type": "regime_review",
            "severity": "warning",
            "message": (
                f"Revisar entradas no regime {row.get('regime')}: "
                f"P&L {row.get('net_pnl'):.2f}, win rate {row.get('win_rate'):.1f}%"
            ),
            "data": row,
        })

    if best_confidence and best_confidence.get("total_trades"):
        recommendations.append({
            "type": "confidence_review",
            "severity": "info",
            "message": (
                f"Bucket de confianca mais forte ate agora: "
                f"{best_confidence.get('confidence_bucket')}-{best_confidence.get('confidence_bucket') + 9}"
            ),
            "data": best_confidence,
        })

    negative_buckets = [
        row for row in confidence
        if (row.get("total_trades") or 0) >= 3 and (row.get("net_pnl") or 0) < 0
    ]
    positive_buckets = [
        row for row in confidence
        if (row.get("total_trades") or 0) >= 3 and (row.get("net_pnl") or 0) > 0
    ]
    if negative_buckets and positive_buckets:
        threshold = min(row.get("confidence_bucket") or 0 for row in positive_buckets)
        bad_below = [
            row for row in negative_buckets
            if (row.get("confidence_bucket") or 0) < threshold
        ]
        if bad_below:
            recommendations.append({
                "type": "confidence_gate",
                "severity": "warning",
                "message": (
                    f"Entradas abaixo de {threshold}% de confianca tiveram P&L fraco; "
                    "IA deve testar bloqueio em paper/shadow por 7 dias antes de aplicar ao live"
                ),
                "data": {"suggested_min_confidence": threshold, "weak_buckets": bad_below},
            })

    if calibration.get("ready"):
        recommendations.append({
            "type": "risk_calibration",
            "severity": "info",
            "message": (
                f"Stop sugerido {calibration.get('suggested_stop_loss_pct')}% e "
                f"take sugerido {calibration.get('suggested_take_profit_pct')}% para validacao automatica"
            ),
            "data": calibration,
        })

    return {
        "mode": "ai_advisory",
        "auto_apply": False,
        "recommendations": recommendations,
    }
