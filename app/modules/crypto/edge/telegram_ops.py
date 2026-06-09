"""Phase 10 — Telegram Quant Ops.

Operationalises quant metrics via Telegram.  Observation-only.
No trades. No orders. No strategy changes.

Notifications:
1. Daily summary   — N, WR, PF, avg_return, readiness, edge_status
2. Edge alerts     — gate crossings (n>=10/30/100), WR<50%, PF<1.5, edge_status change
3. Shadow alerts   — new signal (regime=UNKNOWN, conf 75-84) — handled in forward.py
4. Weekly report   — regimes, buckets, horizons, best/worst segment
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.modules.crypto.edge.alert_state_model import EdgeAlertState
from app.modules.crypto.edge.forward_model import ForwardShadowSignal
from app.modules.crypto.edge.readiness import (
    _edge_icon,
    _readiness_icon,
    _verdict_icon,
    build_readiness_report,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Telegram helper
# ---------------------------------------------------------------------------

_GATE_THRESHOLDS = [10, 30, 100]
_HORIZONS = [24, 72, 168]


def _send_telegram(text: str) -> bool:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    # Phase 12: prefer OPERATIONAL_CHAT_ID; fallback to legacy TELEGRAM_CHAT_ID
    chat_id = (
        os.getenv("OPERATIONAL_CHAT_ID", "")
        or os.getenv("TELEGRAM_CHAT_ID", "")
    )
    enabled = os.getenv("TELEGRAM_ENABLED", "false").lower() in ("1", "true", "yes")
    if not token or not chat_id or not enabled:
        logger.debug("telegram_ops: telegram not configured / disabled")
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        resp = httpx.post(
            url,
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            timeout=10.0,
        )
        ok = resp.status_code == 200
        if not ok:
            logger.warning("telegram_ops: returned %d", resp.status_code)
        return ok
    except Exception as exc:  # noqa: BLE001
        logger.warning("telegram_ops: send failed: %s", exc)
        return False


# ---------------------------------------------------------------------------
# Alert state helpers
# ---------------------------------------------------------------------------


def _now_utc() -> datetime:
    return datetime.now(tz=timezone.utc)


def _get_state(db: Session, key: str) -> dict | None:
    row = db.query(EdgeAlertState).filter(EdgeAlertState.alert_key == key).first()
    return row.last_value if row is not None else None


def _set_state(db: Session, key: str, value: dict) -> None:
    row = db.query(EdgeAlertState).filter(EdgeAlertState.alert_key == key).first()
    now = _now_utc()
    if row is None:
        row = EdgeAlertState(alert_key=key, last_value=value, last_sent_at=now)
        db.add(row)
    else:
        row.last_value = value
        row.last_sent_at = now
        row.updated_at = now
        db.add(row)


def _today_str() -> str:
    return _now_utc().strftime("%Y-%m-%d")


def _iso_week_str() -> str:
    n = _now_utc()
    return f"{n.isocalendar()[0]}-W{n.isocalendar()[1]:02d}"


# ---------------------------------------------------------------------------
# Horizon helpers (reuse from forward_model)
# ---------------------------------------------------------------------------


def _horizon_rows(rows: list[ForwardShadowSignal], h: int) -> list[ForwardShadowSignal]:
    return [s for s in rows if getattr(s, f"outcome_correct_{h}h") is not None]


def _wr(rows: list[ForwardShadowSignal], h: int) -> float | None:
    ev = _horizon_rows(rows, h)
    if not ev:
        return None
    return sum(1 for s in ev if getattr(s, f"outcome_correct_{h}h")) / len(ev)


def _pf(rows: list[ForwardShadowSignal], h: int) -> float | None:
    ev = _horizon_rows(rows, h)
    returns = [
        float(getattr(s, f"return_{h}h"))
        for s in ev
        if getattr(s, f"return_{h}h") is not None
    ]
    wins = [r for r in returns if r > 0]
    losses = [r for r in returns if r < 0]
    if not wins or not losses:
        return None
    return sum(wins) / abs(sum(losses))


def _avg_return(rows: list[ForwardShadowSignal], h: int) -> float | None:
    ev = _horizon_rows(rows, h)
    returns = [
        float(getattr(s, f"return_{h}h"))
        for s in ev
        if getattr(s, f"return_{h}h") is not None
    ]
    return sum(returns) / len(returns) if returns else None


# ---------------------------------------------------------------------------
# 1. Daily Summary
# ---------------------------------------------------------------------------


def _format_daily_summary(
    report: dict, rows: list[ForwardShadowSignal]
) -> str:
    n = report["n_signals_tracked"]
    verdict = report["overall_verdict"]
    readiness = report["overall_readiness"]

    lines = [
        "<b>[Shadow Forward] Resumo Diário</b>",
        f"{_verdict_icon(verdict)} <b>{verdict}</b>  "
        f"{_readiness_icon(readiness)} <b>{readiness}</b>",
        f"N acumulado: <b>{n}</b>",
        "",
    ]
    for label, hdata in report["horizons"].items():
        ne = hdata["n_evaluated"]
        wr = hdata["win_rate"]
        pf = hdata["profit_factor"]
        avg_r = hdata["avg_return_pct"]
        edge = hdata["edge_status"]
        wr_ci = hdata["win_rate_ci_95"]
        icon = _edge_icon(edge)

        wr_str = f"{wr:.1%}" if wr is not None else "N/A"
        pf_str = f"{pf:.2f}" if pf is not None else "N/A"
        avg_str = f"{avg_r:+.2f}%" if avg_r is not None else "N/A"
        ci_str = f"[{wr_ci[0]:.0%},{wr_ci[1]:.0%}]" if wr_ci else "—"
        gates = hdata["gates"]
        gate_str = (
            f"{'✅' if gates['n_ge_10'] else '⬜'}10 "
            f"{'✅' if gates['n_ge_30'] else '⬜'}30 "
            f"{'✅' if gates['n_ge_100'] else '⬜'}100"
        )
        lines += [
            f"<b>{label}</b> {icon} {edge}",
            f"  N={ne} | WR={wr_str} CI={ci_str}",
            f"  PF={pf_str} | avg={avg_str}",
            f"  Gates: {gate_str}",
            "",
        ]

    next_gate = next((g for g in _GATE_THRESHOLDS if g > n), None)
    if next_gate:
        lines.append(f"Próximo gate: n={next_gate} (faltam {next_gate - n})")
    lines.append("Regra: sem trades · apenas observação")
    return "\n".join(lines)


def send_daily_summary(db: Session, force: bool = False) -> dict:
    """Send daily summary at most once per day unless force=True."""
    today = _today_str()
    state = _get_state(db, "daily_summary")
    if not force and state and state.get("date") == today:
        return {"sent": False, "reason": "already_sent_today", "date": today}

    report = build_readiness_report(db)
    rows = db.query(ForwardShadowSignal).all()
    msg = _format_daily_summary(report, rows)
    sent = _send_telegram(msg)

    _set_state(db, "daily_summary", {"date": today, "n": report["n_signals_tracked"]})
    db.commit()

    return {
        "sent": sent,
        "date": today,
        "overall_verdict": report["overall_verdict"],
        "overall_readiness": report["overall_readiness"],
        "n_signals_tracked": report["n_signals_tracked"],
        "message_preview": msg[:300],
    }


# ---------------------------------------------------------------------------
# 2. Edge Alerts
# ---------------------------------------------------------------------------


def _gate_alert_msg(h: int, gate: int, n: int, wr: float | None, pf: float | None) -> str:
    wr_str = f"{wr:.1%}" if wr is not None else "N/A"
    pf_str = f"{pf:.2f}" if pf is not None else "N/A"
    return (
        f"<b>[Shadow Forward] Gate atingido 🎯</b>\n"
        f"Horizonte: <b>{h}h</b> | Gate: <b>n≥{gate}</b> alcançado (n={n})\n"
        f"WR={wr_str} | PF={pf_str}\n"
        "Próximos passos: aguardar estabilização da amostra."
    )


def _edge_change_msg(h: int, old_status: str, new_status: str, n: int, wr: float | None) -> str:
    icon = _edge_icon(new_status)
    wr_str = f"{wr:.1%}" if wr is not None else "N/A"
    return (
        f"<b>[Shadow Forward] Edge status mudou</b>\n"
        f"Horizonte: <b>{h}h</b>\n"
        f"{old_status} → {icon} <b>{new_status}</b>\n"
        f"N={n} | WR={wr_str}"
    )


def _wr_pf_alert_msg(h: int, n: int, wr: float | None, pf: float | None) -> str:
    lines = ["<b>[Shadow Forward] Alerta de métricas ⚠️</b>", f"Horizonte: <b>{h}h</b> | N={n}"]
    if wr is not None and wr < 0.50:
        lines.append(f"❌ WR={wr:.1%} < 50%")
    if pf is not None and pf < 1.5:
        lines.append(f"❌ PF={pf:.2f} < 1.5")
    lines.append("Verificar: amostra pode ser insuficiente.")
    return "\n".join(lines)


def check_and_send_edge_alerts(db: Session) -> dict:
    """Check gate crossings, edge_status changes, WR/PF thresholds and fire Telegram."""
    report = build_readiness_report(db)
    alerts_sent: list[dict] = []

    for h in _HORIZONS:
        label = f"{h}h"
        hdata = report["horizons"][label]
        n_eval = hdata["n_evaluated"]
        edge = hdata["edge_status"]
        wr = hdata["win_rate"]
        pf_val = hdata["profit_factor"]

        # --- Gate crossing ---
        gate_key = f"gate_{h}h"
        gate_state = _get_state(db, gate_key) or {"last_n": 0, "gates_sent": []}
        gates_sent = gate_state.get("gates_sent", [])

        for gate in _GATE_THRESHOLDS:
            if n_eval >= gate and gate not in gates_sent:
                msg = _gate_alert_msg(h, gate, n_eval, wr, pf_val)
                sent = _send_telegram(msg)
                gates_sent.append(gate)
                alerts_sent.append({"type": "gate", "horizon": label, "gate": gate, "sent": sent})

        _set_state(db, gate_key, {"last_n": n_eval, "gates_sent": gates_sent})

        # --- Edge status change ---
        status_key = f"edge_status_{h}h"
        status_state = _get_state(db, status_key) or {"status": None}
        last_status = status_state.get("status")

        if last_status is not None and last_status != edge:
            msg = _edge_change_msg(h, last_status, edge, n_eval, wr)
            sent = _send_telegram(msg)
            alerts_sent.append({
                "type": "edge_change", "horizon": label,
                "from": last_status, "to": edge, "sent": sent,
            })

        _set_state(db, status_key, {"status": edge})

        # --- WR < 50% or PF < 1.5 alert (only after n≥10) ---
        if n_eval >= 10:
            needs_wr_alert = wr is not None and wr < 0.50
            needs_pf_alert = pf_val is not None and pf_val < 1.5
            if needs_wr_alert or needs_pf_alert:
                wr_pf_key = f"wr_pf_alert_{h}h"
                wr_pf_state = _get_state(db, wr_pf_key) or {}
                last_wr = wr_pf_state.get("wr")
                # Only fire if WR degraded or not yet alerted at this level
                if last_wr is None or (wr is not None and wr < last_wr - 0.02):
                    wr_arg = wr if needs_wr_alert else None
                    pf_arg = pf_val if needs_pf_alert else None
                    msg = _wr_pf_alert_msg(h, n_eval, wr_arg, pf_arg)
                    sent = _send_telegram(msg)
                    alerts_sent.append({
                        "type": "wr_pf", "horizon": label,
                        "wr": wr, "pf": pf_val, "sent": sent,
                    })
                    _set_state(db, wr_pf_key, {"wr": wr, "pf": pf_val})

    db.commit()
    return {
        "alerts_checked": len(_HORIZONS),
        "alerts_sent": len(alerts_sent),
        "details": alerts_sent,
    }


# ---------------------------------------------------------------------------
# 3. Weekly Report
# ---------------------------------------------------------------------------


def _regime_breakdown(rows: list[ForwardShadowSignal], h: int) -> dict[str, dict]:
    """Group signals by regime and compute metrics for one horizon."""
    from collections import defaultdict

    groups: dict[str, list[ForwardShadowSignal]] = defaultdict(list)
    for s in rows:
        regime = s.regime or "UNKNOWN"
        groups[regime].append(s)

    result: dict[str, dict] = {}
    for regime, group in groups.items():
        ev = [s for s in group if getattr(s, f"outcome_correct_{h}h") is not None]
        n = len(group)
        n_ev = len(ev)
        wr = sum(1 for s in ev if getattr(s, f"outcome_correct_{h}h")) / n_ev if n_ev else None
        result[regime] = {"n": n, "n_evaluated": n_ev, "win_rate": wr}
    return result


def _confidence_breakdown(rows: list[ForwardShadowSignal], h: int) -> dict[str, dict]:
    """Group by confidence bucket."""
    from collections import defaultdict

    def _bucket(conf: int | None) -> str:
        if conf is None:
            return "N/A"
        if conf < 75:
            return "<75"
        if conf <= 84:
            return "75-84"
        return "85+"

    groups: dict[str, list[ForwardShadowSignal]] = defaultdict(list)
    for s in rows:
        groups[_bucket(s.confidence)].append(s)

    result: dict[str, dict] = {}
    for bucket, group in sorted(groups.items()):
        ev = [s for s in group if getattr(s, f"outcome_correct_{h}h") is not None]
        n_ev = len(ev)
        wr = sum(1 for s in ev if getattr(s, f"outcome_correct_{h}h")) / n_ev if n_ev else None
        result[bucket] = {"n": len(group), "n_evaluated": n_ev, "win_rate": wr}
    return result


def _best_worst_segment(report: dict) -> tuple[str, str]:
    """Return (best_label, worst_label) by win_rate among evaluated horizons."""
    evaluated = {
        k: v["win_rate"]
        for k, v in report["horizons"].items()
        if v["win_rate"] is not None
    }
    if not evaluated:
        return ("N/A", "N/A")
    best = max(evaluated, key=lambda k: evaluated[k])
    worst = min(evaluated, key=lambda k: evaluated[k])
    return (best, worst)


def _format_weekly_report(
    report: dict,
    rows: list[ForwardShadowSignal],
    week_str: str,
) -> str:
    n = report["n_signals_tracked"]
    verdict = report["overall_verdict"]
    readiness = report["overall_readiness"]
    best, worst = _best_worst_segment(report)

    lines = [
        "<b>[Shadow Forward] Relatório Semanal</b>",
        f"Semana: <b>{week_str}</b> | N acumulado: <b>{n}</b>",
        f"{_verdict_icon(verdict)} <b>{verdict}</b>  "
        f"{_readiness_icon(readiness)} <b>{readiness}</b>",
        "",
        "<b>HORIZONS</b>",
    ]

    for label, hdata in report["horizons"].items():
        wr = hdata["win_rate"]
        pf = hdata["profit_factor"]
        avg_r = hdata["avg_return_pct"]
        edge = hdata["edge_status"]
        icon = _edge_icon(edge)
        wr_str = f"{wr:.1%}" if wr is not None else "N/A"
        pf_str = f"{pf:.2f}" if pf is not None else "N/A"
        avg_str = f"{avg_r:+.2f}%" if avg_r is not None else "N/A"
        best_mark = " ★" if label == best else ""
        worst_mark = " ✗" if label == worst else ""
        lines.append(
            f"  {label}: WR={wr_str} PF={pf_str} avg={avg_str} "
            f"{icon}{best_mark}{worst_mark}"
        )

    lines += ["", "<b>REGIMES (72h)</b>"]
    for regime, rdata in _regime_breakdown(rows, 72).items():
        wr_str = f"{rdata['win_rate']:.1%}" if rdata["win_rate"] is not None else "N/A"
        lines.append(f"  {regime}: n={rdata['n']} WR={wr_str}")

    lines += ["", "<b>CONFIANÇA (72h)</b>"]
    for bucket, bdata in _confidence_breakdown(rows, 72).items():
        wr_str = f"{bdata['win_rate']:.1%}" if bdata["win_rate"] is not None else "N/A"
        lines.append(f"  conf {bucket}: n={bdata['n']} WR={wr_str}")

    lines += [
        "",
        f"Melhor: <b>{best}</b>  |  Pior: <b>{worst}</b>",
    ]

    next_gate = next((g for g in _GATE_THRESHOLDS if g > n), None)
    if next_gate:
        lines.append(f"Próximo gate: n={next_gate} (faltam {next_gate - n})")

    lines.append("Regra: sem trades · apenas observação")
    return "\n".join(lines)


def send_weekly_report(db: Session, force: bool = False) -> dict:
    """Send weekly report at most once per ISO week unless force=True."""
    week = _iso_week_str()
    state = _get_state(db, "weekly_report")
    if not force and state and state.get("week") == week:
        return {"sent": False, "reason": "already_sent_this_week", "week": week}

    report = build_readiness_report(db)
    rows = db.query(ForwardShadowSignal).order_by(ForwardShadowSignal.signal_at).all()
    msg = _format_weekly_report(report, rows, week)
    sent = _send_telegram(msg)

    _set_state(db, "weekly_report", {"week": week, "n": report["n_signals_tracked"]})
    db.commit()

    return {
        "sent": sent,
        "week": week,
        "overall_verdict": report["overall_verdict"],
        "overall_readiness": report["overall_readiness"],
        "n_signals_tracked": report["n_signals_tracked"],
        "message_preview": msg[:400],
    }


# ---------------------------------------------------------------------------
# Convenience: run all ops in one call
# ---------------------------------------------------------------------------


def run_all_ops(db: Session, force: bool = False) -> dict:
    """Run daily summary + edge alerts in one call.  Weekly only on Monday."""
    daily = send_daily_summary(db, force=force)
    alerts = check_and_send_edge_alerts(db)

    weekly: dict[str, Any] = {}
    if force or _now_utc().weekday() == 0:  # 0 = Monday
        weekly = send_weekly_report(db, force=force)

    return {
        "daily": daily,
        "alerts": alerts,
        "weekly": weekly,
    }
