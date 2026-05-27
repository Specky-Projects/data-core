"""Alert detection and per-type cooldown management for immediate Telegram alerts.

Design
──────
  • AlertService holds in-memory cooldown state (threading.Lock protected)
  • A module-level singleton is used across scheduler job invocations
  • Alert conditions are evaluated against OperationalSummaryPayload
  • Each alert_type has an independent cooldown (critical: 15min, warning: 60min)
  • Alerts suppressed by cooldown are counted in prometheus (telegram_rate_limited_total)

Rules
─────
  NEVER raise from evaluate() — caller must not crash on condition check
  ALWAYS check cooldown before returning an alert
  ALWAYS use the singleton via get_alert_service() (thread-safe double-check lock)
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from typing import Callable, NamedTuple

from app.telegram_summary.dto import AlertPayload, OperationalSummaryPayload, QuantSummaryPayload

logger = logging.getLogger(__name__)

# Cooldown per severity (minutes)
_COOLDOWN_MINUTES: dict[str, int] = {
    "critical": 15,
    "warning": 60,
}

_SummaryArgs = tuple[OperationalSummaryPayload, QuantSummaryPayload | None]


class _AlertRule(NamedTuple):
    alert_type: str
    severity: str
    title: str
    condition: Callable[[OperationalSummaryPayload, QuantSummaryPayload | None], str | None]
    details: Callable[[OperationalSummaryPayload, QuantSummaryPayload | None], dict]


# ── Condition functions ────────────────────────────────────────────────────────

def _cond_system_critical(op: OperationalSummaryPayload, _: QuantSummaryPayload | None) -> str | None:
    if op.status == "CRITICAL":
        return (
            f"Status crítico detectado. Score: {op.confidence_score}/100. "
            f"Findings: {len(op.critical_findings)}. Status: {op.operational_status}."
        )
    return None


def _cond_safe_mode(op: OperationalSummaryPayload, _: QuantSummaryPayload | None) -> str | None:
    if op.safe_mode:
        return (
            f"Sistema em Safe Mode. Score: {op.confidence_score}/100. "
            f"Status: {op.operational_status}."
        )
    return None


def _cond_low_replayability(op: OperationalSummaryPayload, _: QuantSummaryPayload | None) -> str | None:
    if op.replayability_score < 60:
        return (
            f"Replayability score: {op.replayability_score}/100 (limiar: 60). "
            "BOOST bloqueado. Verificar /health/replayability."
        )
    return None


def _cond_quant_critical(op: OperationalSummaryPayload, _: QuantSummaryPayload | None) -> str | None:
    if op.quant_reliability_score < 40:
        return (
            f"Quant reliability: {op.quant_reliability_score}/100 (limiar crítico: 40). "
            "Qualidade do sinal comprometida."
        )
    return None


def _cond_low_confidence(op: OperationalSummaryPayload, _: QuantSummaryPayload | None) -> str | None:
    if op.confidence_score < 50:
        return (
            f"Confidence score baixo: {op.confidence_score}/100 (limiar: 50). "
            "Verificar /health/operational."
        )
    return None


def _details_op(op: OperationalSummaryPayload, _: QuantSummaryPayload | None) -> dict:
    return {
        "Score": f"{op.confidence_score}/100",
        "Runtime": op.runtime_score,
        "Dataset": op.dataset_score,
        "Status": op.operational_status,
    }


# ── Rules registry ─────────────────────────────────────────────────────────────

_RULES: list[_AlertRule] = [
    _AlertRule(
        alert_type="system_critical",
        severity="critical",
        title="Sistema em Estado Crítico",
        condition=_cond_system_critical,
        details=_details_op,
    ),
    _AlertRule(
        alert_type="safe_mode_activated",
        severity="warning",
        title="Safe Mode Ativo",
        condition=_cond_safe_mode,
        details=_details_op,
    ),
    _AlertRule(
        alert_type="low_replayability",
        severity="warning",
        title="Replayability Abaixo do Limiar",
        condition=_cond_low_replayability,
        details=lambda op, _: {
            "Replayability": f"{op.replayability_score}/100",
            "Limiar": "60",
            "BOOST": "bloqueado",
        },
    ),
    _AlertRule(
        alert_type="quant_critical",
        severity="critical",
        title="Quant Reliability Crítico",
        condition=_cond_quant_critical,
        details=lambda op, _: {
            "Quant Score": f"{op.quant_reliability_score}/100",
            "Limiar Crítico": "40",
        },
    ),
    _AlertRule(
        alert_type="low_confidence",
        severity="warning",
        title="Confidence Score Baixo",
        condition=_cond_low_confidence,
        details=_details_op,
    ),
]


# ── AlertService ───────────────────────────────────────────────────────────────

class AlertService:
    """Detect alert conditions and enforce per-type cooldown.

    Thread-safe: all state mutations use self._lock.
    """

    def __init__(self) -> None:
        self._cooldown_state: dict[str, datetime] = {}
        self._lock = threading.Lock()

    def is_on_cooldown(self, alert_type: str, severity: str) -> bool:
        """Return True if this alert_type was recently sent and is still cooling down."""
        cooldown_min = _COOLDOWN_MINUTES.get(severity, 60)
        now = datetime.now(timezone.utc)
        with self._lock:
            last_sent = self._cooldown_state.get(alert_type)
            if last_sent is None:
                return False
            return (now - last_sent) < timedelta(minutes=cooldown_min)

    def mark_sent(self, alert_type: str) -> None:
        """Record that this alert_type was just sent (resets cooldown timer)."""
        now = datetime.now(timezone.utc)
        with self._lock:
            self._cooldown_state[alert_type] = now

    def evaluate(
        self,
        operational: OperationalSummaryPayload,
        quant: QuantSummaryPayload | None = None,
    ) -> list[AlertPayload]:
        """Evaluate all alert conditions; return those that are active AND off-cooldown.

        Never raises — failures per rule are caught and logged individually.
        """
        alerts: list[AlertPayload] = []
        for rule in _RULES:
            try:
                message = rule.condition(operational, quant)
                if message is None:
                    continue  # condition not triggered
                if self.is_on_cooldown(rule.alert_type, rule.severity):
                    logger.debug(
                        "telegram_summary: alert suppressed by cooldown — %s", rule.alert_type
                    )
                    try:
                        from app.telegram_summary.metrics import telegram_rate_limited_total
                        telegram_rate_limited_total.labels(alert_type=rule.alert_type).inc()
                    except Exception:
                        pass
                    continue
                details = rule.details(operational, quant)
                alerts.append(AlertPayload(
                    alert_type=rule.alert_type,
                    severity=rule.severity,
                    title=rule.title,
                    message=message,
                    details=details,
                ))
            except Exception:
                logger.exception("telegram_summary: alert rule evaluation failed — %s", rule.alert_type)
        return alerts


# ── Singleton ──────────────────────────────────────────────────────────────────

_singleton: AlertService | None = None
_singleton_lock = threading.Lock()


def get_alert_service() -> AlertService:
    """Return the module-level AlertService singleton (thread-safe)."""
    global _singleton
    if _singleton is None:
        with _singleton_lock:
            if _singleton is None:
                _singleton = AlertService()
    return _singleton
