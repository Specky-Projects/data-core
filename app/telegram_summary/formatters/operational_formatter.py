"""Format OperationalSummaryPayload into a ≤20-line HTML Telegram message.

Output example
──────────────
📊 <b>Resumo Operacional</b> — 14:00 UTC

Status: ✅ HEALTHY  (92/100)
Runtime: 88  |  Dataset: 95  |  Replay: 90
Quant: 87  |  Infra: 100  |  Seg: 95

Safe Mode: 🟢 off  |  Degradação: Não
🔴 Críticos: 0   ⚠️ Avisos: 0

<i>data-core · env:production · 1h</i>
"""

from __future__ import annotations

from app.telegram_summary.dto import OperationalSummaryPayload

_STATUS_ICON: dict[str, str] = {
    "OK": "✅",
    "WARNING": "⚠️",
    "CRITICAL": "🔴",
}

_OP_ICON: dict[str, str] = {
    "HEALTHY": "🟢",
    "DEGRADED": "🟡",
    "PARTIALLY_UNSAFE": "🟠",
    "UNSAFE": "🔴",
    "CRITICAL": "💀",
}


def format_operational_summary(payload: OperationalSummaryPayload) -> str:
    """Return an HTML-formatted operational health summary (≤20 lines)."""
    ts = payload.generated_at.strftime("%H:%M UTC")
    s_icon = _STATUS_ICON.get(payload.status, "❔")
    safe = "🔴 ATIVO" if payload.safe_mode else "🟢 off"
    degraded = "Sim ⚠️" if payload.degradation_detected else "Não"

    n_critical = len(payload.critical_findings)
    n_warn = len(payload.warnings)

    lines: list[str] = [
        f"📊 <b>Resumo Operacional</b> — {ts}",
        "",
        f"Status: {s_icon} {payload.operational_status}  ({payload.confidence_score}/100)",
        f"Runtime: {payload.runtime_score}  |  Dataset: {payload.dataset_score}  |  Replay: {payload.replayability_score}",
        f"Quant: {payload.quant_reliability_score}  |  Infra: {payload.infra_score}  |  Seg: {payload.security_score}",
        "",
        f"Safe Mode: {safe}  |  Degradação: {degraded}",
        f"🔴 Críticos: {n_critical}   ⚠️ Avisos: {n_warn}",
    ]

    # Include up to 3 critical findings (truncated to 60 chars each)
    if payload.critical_findings:
        lines.append("")
        for finding in payload.critical_findings[:3]:
            lines.append(f"  • {finding[:60]}")

    lines += ["", f"<i>data-core · env:{payload.environment} · {payload.window_hours}h</i>"]
    return "\n".join(lines)
