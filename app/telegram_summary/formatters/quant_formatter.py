"""Format QuantSummaryPayload into a ≤20-line HTML Telegram message.

Output example
──────────────
📈 <b>Resumo Quant</b> — 12:00 UTC

Outcomes: 142 (últimos 30d)
Win Rate: 62.3%  |  PF: 1.82
Expectancy: +0.430  |  Max DD: 2.1%

Regime: trending  |  Risco: 🟢 LOW
BOOST: ✅ permitido  |  Calibrado: Sim
Top: BTCUSDT, ETHUSDT

Rec: ✅ KEEP

<i>data-core · adaptive intelligence</i>
"""

from __future__ import annotations

from app.telegram_summary.dto import QuantSummaryPayload

_RISK_ICON: dict[str, str] = {
    "LOW": "🟢",
    "MEDIUM": "🟡",
    "HIGH": "🟠",
    "CRITICAL": "🔴",
}

_REC_ICON: dict[str, str] = {
    "BOOST": "🚀",
    "KEEP": "✅",
    "THROTTLE": "⚠️",
    "DISABLE": "🚫",
    "OBSERVE_ONLY": "👁️",
}


def format_quant_summary(payload: QuantSummaryPayload) -> str:
    """Return an HTML-formatted quant summary (≤20 lines)."""
    ts = payload.generated_at.strftime("%H:%M UTC")
    risk_icon = _RISK_ICON.get(payload.risk_level, "❔")
    rec_icon = _REC_ICON.get(payload.overall_recommendation, "❔")
    boost = "🚫 bloqueado" if payload.boost_blocked else "✅ permitido"
    calibrated = "Sim" if payload.calibrated else "Não"

    wr = f"{payload.win_rate:.1%}" if payload.win_rate is not None else "N/A"
    pf = f"{payload.profit_factor:.2f}" if payload.profit_factor is not None else "N/A"
    ex = f"{payload.expectancy:+.3f}" if payload.expectancy is not None else "N/A"
    dd = f"{payload.max_drawdown_pct:.1f}%" if payload.max_drawdown_pct is not None else "N/A"

    lines: list[str] = [
        f"📈 <b>Resumo Quant</b> — {ts}",
        "",
        f"Outcomes: {payload.total_outcomes} (últimos {payload.lookback_days}d)",
        f"Win Rate: {wr}  |  PF: {pf}",
        f"Expectancy: {ex}  |  Max DD: {dd}",
        "",
        f"Regime: {payload.dominant_regime or 'N/A'}  |  Risco: {risk_icon} {payload.risk_level}",
        f"BOOST: {boost}  |  Calibrado: {calibrated}",
    ]

    if payload.top_symbols:
        lines.append(f"Top: {', '.join(payload.top_symbols[:3])}")

    lines += [
        "",
        f"Rec: {rec_icon} {payload.overall_recommendation}",
        "",
        "<i>data-core · adaptive intelligence</i>",
    ]
    return "\n".join(lines)
