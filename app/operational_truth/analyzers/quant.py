"""QuantReliabilityAnalyzer — fetches quant truth from poupi-crypto via internal HTTP.

Gracefully degrades to a conservative score when the service is unavailable.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

import httpx

from app.operational_truth.dto import QuantTruth, classify_score

logger = logging.getLogger(__name__)

POUPI_CRYPTO_URL = os.getenv("POUPI_CRYPTO_INTERNAL_URL", "http://poupi-crypto-api:8002")
_REQUEST_TIMEOUT = 3.0  # seconds


def _fetch_crypto_status() -> dict | None:
    """Fetch /system-status from poupi-crypto. Returns None if unavailable."""
    try:
        url = f"{POUPI_CRYPTO_URL}/system-status"
        with httpx.Client(timeout=_REQUEST_TIMEOUT) as client:
            resp = client.get(url)
            if resp.status_code == 200:
                return resp.json()
    except Exception as exc:
        logger.debug("quant_analyzer: poupi-crypto unavailable: %s", exc)
    return None


def _fetch_crypto_metrics_text() -> str | None:
    """Fetch /metrics (Prometheus text) from poupi-crypto for direct gauge reads."""
    try:
        url = f"{POUPI_CRYPTO_URL}/metrics"
        with httpx.Client(timeout=_REQUEST_TIMEOUT) as client:
            resp = client.get(url)
            if resp.status_code == 200:
                return resp.text
    except Exception:
        pass
    return None


def _parse_gauge(metrics_text: str, name: str) -> float | None:
    """Parse a single Prometheus gauge value from text format."""
    for line in metrics_text.splitlines():
        if line.startswith(name + " ") or line.startswith(name + "{"):
            parts = line.rsplit(" ", 1)
            if len(parts) == 2:
                try:
                    return float(parts[1])
                except ValueError:
                    pass
    return None


def _degraded_quant(reason: str) -> QuantTruth:
    return QuantTruth(
        score=40,
        status="PARTIALLY_UNSAFE",
        source="unavailable",
        confidence_drift_detected=False,
        entropy_spike_detected=False,
        invalid_decision_ratio=0.0,
        hold_effectiveness=None,
        calibration_ok=False,
        strategy_stable=False,
        findings=[f"quant_unavailable: {reason}"],
        evaluated_at=datetime.now(timezone.utc),
    )


def analyze_quant() -> QuantTruth:
    now = datetime.now(timezone.utc)
    findings: list[str] = []

    status_data = _fetch_crypto_status()
    metrics_text = _fetch_crypto_metrics_text()

    if status_data is None and metrics_text is None:
        return _degraded_quant("poupi-crypto unreachable")

    source = "live"

    # ── Parse from system-status ───────────────────────────────────────────────
    safety = status_data.get("safety", {}) if status_data else {}
    dry_run = safety.get("dry_run", True)

    # ── Parse from Prometheus metrics ─────────────────────────────────────────
    invalid_decision_ratio_val = 0.0
    hold_eff: float | None = None
    confidence_drift = False
    entropy_spike = False
    calibration_ok = True
    strategy_stable = True

    if metrics_text:
        # invalid decision ratio gauge
        v = _parse_gauge(metrics_text, "poupi_crypto_signal_rejections_total")
        analyzed = _parse_gauge(metrics_text, "poupi_crypto_signals_analyzed_total")
        if v is not None and analyzed and analyzed > 0:
            invalid_decision_ratio_val = min(1.0, v / analyzed)
            if invalid_decision_ratio_val > 0.7:
                findings.append(f"invalid_decision_ratio_high: {invalid_decision_ratio_val:.2f}")
                confidence_drift = True
            elif invalid_decision_ratio_val > 0.5:
                findings.append(f"invalid_decision_ratio_elevated: {invalid_decision_ratio_val:.2f}")

        # near-miss signals spike can indicate entropy issues
        near_miss = _parse_gauge(metrics_text, "poupi_crypto_signal_near_miss_total")
        generated = _parse_gauge(metrics_text, "poupi_crypto_signals_generated_total")
        if near_miss is not None and generated is not None and generated > 0:
            near_miss_ratio = near_miss / max(generated, 1)
            if near_miss_ratio > 0.8:
                entropy_spike = True
                findings.append(f"entropy_spike: near-miss ratio {near_miss_ratio:.2f}")

    # Assess overall quant health from system-status
    if status_data:
        overall = status_data.get("overall", "")
        if overall in ("BLOCKED", "NO-GO"):
            strategy_stable = False
            findings.append(f"quant_overall_status: {overall}")
        elif overall == "DEGRADED":
            strategy_stable = False
            findings.append("quant_strategy_degraded")

    # Score
    score = 100
    if not calibration_ok:
        score -= 20
    if confidence_drift:
        score -= 25
    if entropy_spike:
        score -= 20
    if invalid_decision_ratio_val > 0.7:
        score -= 20
    elif invalid_decision_ratio_val > 0.5:
        score -= 10
    if not strategy_stable:
        score -= 15
    if dry_run:
        score = max(score, 50)  # dry_run means no real risk from bad decisions

    score = max(0, score)
    return QuantTruth(
        score=score,
        status=classify_score(score),
        source=source,
        confidence_drift_detected=confidence_drift,
        entropy_spike_detected=entropy_spike,
        invalid_decision_ratio=invalid_decision_ratio_val,
        hold_effectiveness=hold_eff,
        calibration_ok=calibration_ok,
        strategy_stable=strategy_stable,
        findings=findings,
        evaluated_at=now,
    )
