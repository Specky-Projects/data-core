"""
Pure analytics helpers — no ORM imports.

Reused by NBA and WNBA analytics modules.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.modules.basketball.shared.enums import EdgeClassification

# 200 settled bets is the practical minimum for a one-sided binomial test
# to have ~80% power detecting a 5pp edge over the 52.38% break-even at α=0.05.
MIN_BETS_FOR_CLASSIFICATION = 200
PROFITABLE_ROI = 5.0
LOSING_ROI = -5.0


@dataclass
class SetupAnalytics:
    setup_name: str
    total_bets: int
    wins: int
    losses: int
    pending: int
    void: int
    roi: float
    yield_pct: float
    win_rate: float
    profit_factor: float
    expectancy: float
    max_drawdown: float
    classification: str


@dataclass
class GlobalAnalytics:
    total_signals: int
    total_bets: int
    wins: int
    losses: int
    pending: int
    void: int
    roi: float
    pnl: float
    win_rate: float
    setups: list[SetupAnalytics] = field(default_factory=list)


def drawdown(pnl_seq: list[float]) -> float:
    if not pnl_seq:
        return 0.0
    peak = 0.0
    cum = 0.0
    dd = 0.0
    for p in pnl_seq:
        cum += p
        if cum > peak:
            peak = cum
        dd = max(dd, peak - cum)
    return round(dd, 4)


def classify(roi: float, total: int) -> EdgeClassification:
    if total < MIN_BETS_FOR_CLASSIFICATION:
        return EdgeClassification.neutral
    if roi >= PROFITABLE_ROI:
        return EdgeClassification.profitable
    if roi <= LOSING_ROI:
        return EdgeClassification.losing
    return EdgeClassification.neutral
