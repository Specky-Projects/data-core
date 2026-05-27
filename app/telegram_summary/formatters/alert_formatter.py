"""Format AlertPayload into a ≤20-line HTML Telegram message.

Output example (warning)
────────────────────────
⚠️ <b>Alerta: Safe Mode Ativo</b>

Sistema em Safe Mode. Score: 58/100. Status: DEGRADED

  <b>Score:</b> 58/100
  <b>Runtime:</b> 72
  <b>Dataset:</b> 90
  <b>Status:</b> DEGRADED

<i>27/05/2026 14:32 UTC · data-core</i>
"""

from __future__ import annotations

from app.telegram_summary.dto import AlertPayload

_SEVERITY_ICON: dict[str, str] = {
    "warning": "⚠️",
    "critical": "🚨",
}


def format_alert(payload: AlertPayload) -> str:
    """Return an HTML-formatted immediate alert message (≤20 lines)."""
    icon = _SEVERITY_ICON.get(payload.severity, "❔")
    ts = payload.generated_at.strftime("%d/%m/%Y %H:%M UTC")

    lines: list[str] = [
        f"{icon} <b>Alerta: {payload.title}</b>",
        "",
        payload.message,
    ]

    if payload.details:
        lines.append("")
        for key, value in list(payload.details.items())[:5]:  # max 5 detail lines
            lines.append(f"  <b>{key}:</b> {value}")

    lines += ["", f"<i>{ts} · data-core</i>"]
    return "\n".join(lines)
