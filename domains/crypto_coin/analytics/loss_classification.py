"""Heuristics to classify losing trades for later tuning."""

from __future__ import annotations


def classify_loss(
    *,
    pnl_pct: float | None,
    signal: str | None = None,
    mae: float | None = None,
    mfe: float | None = None,
    slippage: float | None = None,
    fee: float | None = None,
    regime: str | None = None,
) -> str | None:
    if pnl_pct is None or pnl_pct >= 0:
        return None

    friction = abs(slippage or 0.0) + abs(fee or 0.0)
    if abs(pnl_pct) <= max(0.15, friction * 2) and friction > 0:
        return "slippage_fee_killed_trade"

    regime_text = str(regime or "").lower()
    if "lateral" in regime_text:
        return "sideways_market"

    if signal and "STOP" in signal.upper():
        if mfe is not None and mfe > abs(pnl_pct):
            return "late_exit_or_gave_back_profit"
        return "valid_technical_stop"

    if mfe is not None and mfe > 0 and mae is not None and abs(mae) < abs(pnl_pct) * 1.2:
        return "stop_too_tight"

    if mfe is not None and mfe < 0.25:
        return "false_breakout"

    return "late_entry"
