"""Payload dataclasses for Telegram summary messages.

Each payload contains pre-aggregated, ready-to-format data.
Formatters consume payloads and produce HTML strings — they never query the DB.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── Operational (hourly) ───────────────────────────────────────────────────────

@dataclass
class OperationalSummaryPayload:
    """Aggregated operational health data for the hourly summary."""

    status: str                  # ReadinessStatus: OK | WARNING | CRITICAL
    operational_status: str      # HEALTHY | DEGRADED | PARTIALLY_UNSAFE | UNSAFE | CRITICAL
    confidence_score: int
    runtime_score: int
    dataset_score: int
    replayability_score: int
    quant_reliability_score: int
    infra_score: int
    security_score: int
    safe_mode: bool
    degradation_detected: bool
    critical_findings: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    generated_at: datetime = field(default_factory=_now)
    window_hours: int = 1
    environment: str = "production"


# ── Quant (6h) ────────────────────────────────────────────────────────────────

@dataclass
class QuantSummaryPayload:
    """Aggregated quant/adaptive intelligence data for the 6h summary."""

    total_outcomes: int
    lookback_days: int = 30
    win_rate: float | None = None          # fraction 0-1
    expectancy: float | None = None
    profit_factor: float | None = None
    avg_return_pct: float | None = None
    max_drawdown_pct: float | None = None  # already a % value (e.g. 2.1 = 2.1%)
    dominant_regime: str | None = None
    top_symbols: list[str] = field(default_factory=list)
    overall_recommendation: str = "OBSERVE_ONLY"
    risk_level: str = "LOW"
    boost_blocked: bool = True
    calibrated: bool = False
    generated_at: datetime = field(default_factory=_now)


# ── Longitudinal (daily) ──────────────────────────────────────────────────────

@dataclass
class LongitudinalSummaryPayload:
    """Two-window comparison (24h vs 7d) for the daily digest."""

    outcomes_24h: int
    outcomes_7d: int
    win_rate_24h: float | None = None      # fraction 0-1
    win_rate_7d: float | None = None
    expectancy_24h: float | None = None
    expectancy_7d: float | None = None
    profit_factor_24h: float | None = None
    profit_factor_7d: float | None = None
    max_drawdown_24h: float | None = None  # % value
    max_drawdown_7d: float | None = None
    dominant_regime_24h: str | None = None
    dominant_regime_7d: str | None = None
    generated_at: datetime = field(default_factory=_now)


# ── Alerts (immediate) ────────────────────────────────────────────────────────

@dataclass
class AlertPayload:
    """Payload for an immediate alert message."""

    alert_type: str
    severity: str              # "warning" | "critical"
    title: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    generated_at: datetime = field(default_factory=_now)
