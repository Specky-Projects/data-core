"""Format LongitudinalSummaryPayload into a ≤20-line HTML Telegram message.

Output example
──────────────
📅 <b>Resumo Longitudinal</b> — 27/05/2026

<b>Outcomes:</b>   24h: 12     |  7d: 87
<b>Win Rate:</b>   24h: 65.0%  |  7d: 61.2%  ⬆️ +3.8pp
<b>Expectancy:</b> 24h: +0.52  |  7d: +0.41  ⬆️ +0.11
<b>PF:</b>         24h: 2.10   |  7d: 1.80   ⬆️ +0.30
<b>Max DD:</b>     24h: 1.5%   |  7d: 2.3%   ⬇️ -0.80
<b>Regime:</b>     24h: trending | 7d: ranging

<i>data-core · digest diário</i>
"""

from __future__ import annotations

from app.telegram_summary.dto import LongitudinalSummaryPayload


def _delta_pp(v24: float | None, v7: float | None) -> str:
    """Delta for fraction values (win_rate 0-1): display in percentage points."""
    if v24 is None or v7 is None:
        return ""
    delta = (v24 - v7) * 100
    if abs(delta) < 0.05:
        return "≈"
    arrow = "⬆️" if delta > 0 else "⬇️"
    return f"{arrow} {delta:+.1f}pp"


def _delta_num(v24: float | None, v7: float | None) -> str:
    """Delta for plain numeric values (expectancy, PF, etc.)."""
    if v24 is None or v7 is None:
        return ""
    delta = v24 - v7
    if abs(delta) < 0.005:
        return "≈"
    arrow = "⬆️" if delta > 0 else "⬇️"
    return f"{arrow} {delta:+.2f}"


def _pct(v: float | None) -> str:
    return f"{v:.1%}" if v is not None else "N/A"


def _num(v: float | None, sign: bool = False) -> str:
    if v is None:
        return "N/A"
    return f"{v:+.2f}" if sign else f"{v:.2f}"


def _pct_val(v: float | None) -> str:
    """For % values already in % unit (e.g. max_drawdown_pct=2.1 → '2.1%')."""
    return f"{v:.1f}%" if v is not None else "N/A"


def format_longitudinal_summary(payload: LongitudinalSummaryPayload) -> str:
    """Return an HTML-formatted longitudinal digest (≤20 lines)."""
    date_str = payload.generated_at.strftime("%d/%m/%Y")

    wr_d = _delta_pp(payload.win_rate_24h, payload.win_rate_7d)
    ex_d = _delta_num(payload.expectancy_24h, payload.expectancy_7d)
    pf_d = _delta_num(payload.profit_factor_24h, payload.profit_factor_7d)
    dd_d = _delta_num(payload.max_drawdown_24h, payload.max_drawdown_7d)

    r24 = payload.dominant_regime_24h or "N/A"
    r7d = payload.dominant_regime_7d or "N/A"

    lines: list[str] = [
        f"📅 <b>Resumo Longitudinal</b> — {date_str}",
        "",
        f"<b>Outcomes:</b>   24h: {payload.outcomes_24h:<6}  |  7d: {payload.outcomes_7d}",
        f"<b>Win Rate:</b>   24h: {_pct(payload.win_rate_24h):<7}  |  7d: {_pct(payload.win_rate_7d):<7}  {wr_d}",
        f"<b>Expectancy:</b> 24h: {_num(payload.expectancy_24h, sign=True):<7}  |  7d: {_num(payload.expectancy_7d, sign=True):<7}  {ex_d}",
        f"<b>PF:</b>         24h: {_num(payload.profit_factor_24h):<7}  |  7d: {_num(payload.profit_factor_7d):<7}  {pf_d}",
        f"<b>Max DD:</b>     24h: {_pct_val(payload.max_drawdown_24h):<7}  |  7d: {_pct_val(payload.max_drawdown_7d):<7}  {dd_d}",
        f"<b>Regime:</b>     24h: {r24:<10}  |  7d: {r7d}",
        "",
        "<i>data-core · digest diário</i>",
    ]
    return "\n".join(lines)
