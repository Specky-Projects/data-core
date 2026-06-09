"""
Out-of-sample validation for NBA Quant setups.

Methodology:
  - Train window: 2022, 2023 (in-sample calibration)
  - Test window:  2024       (out-of-sample, never touched during signal design)

Metrics per window:
  - win_rate      : wins / (wins + losses)
  - roi           : (pnl / staked) * 100
  - profit_factor : gross_profit / gross_loss  (> 1.0 is profitable)
  - max_drawdown  : max peak-to-trough of cumulative PnL series (in stake units)
  - sharpe        : mean(pnl_per_bet) / std(pnl_per_bet)   (per-bet, unannualized)
  - sample_size   : total settled bets

Verdict classification:
  - EDGE_CONFIRMED  : OOS ROI > 0 and win_rate > 52% and sample_size >= 30
  - EDGE_MARGINAL   : OOS ROI > 0 OR win_rate > 52% but not both, or sample < 30
  - EDGE_DEGRADED   : IS profitable but OOS negative
  - NO_EDGE         : both IS and OOS negative
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Literal

from sqlalchemy.orm import Session

from app.modules.nba.quant.models import BetStatus, NbaGame, NbaQuantBet, NbaSignal

# Minimum samples for a statistically meaningful verdict
_MIN_SAMPLE = 30
# Minimum win rate needed to beat -110 vig (~52.4%)
_VIG_BREAKEVEN = 0.524


@dataclass
class WindowMetrics:
    """Betting metrics for one time window (train or test)."""
    seasons: list[int]
    sample_size: int = 0
    wins: int = 0
    losses: int = 0
    win_rate: float = 0.0
    roi: float = 0.0          # %
    profit_factor: float = 0.0
    max_drawdown: float = 0.0
    sharpe: float = 0.0
    total_staked: float = 0.0
    total_pnl: float = 0.0


@dataclass
class SetupOOSResult:
    """Full OOS result for one setup."""
    setup_name: str
    train: WindowMetrics
    test: WindowMetrics
    verdict: Literal["EDGE_CONFIRMED", "EDGE_MARGINAL", "EDGE_DEGRADED", "NO_EDGE"] = "NO_EDGE"
    notes: list[str] = field(default_factory=list)


def _compute_metrics(bets: list[NbaQuantBet], seasons: list[int]) -> WindowMetrics:
    """Compute all metrics from a list of settled NbaQuantBet objects."""
    settled = [b for b in bets if b.status in (BetStatus.won, BetStatus.lost)]
    m = WindowMetrics(seasons=seasons, sample_size=len(settled))

    if not settled:
        return m

    m.wins = sum(1 for b in settled if b.status == BetStatus.won)
    m.losses = sum(1 for b in settled if b.status == BetStatus.lost)
    m.win_rate = m.wins / len(settled) if settled else 0.0

    pnls = [float(b.pnl or 0) for b in settled]
    stakes = [float(b.stake or 1) for b in settled]
    m.total_pnl = sum(pnls)
    m.total_staked = sum(stakes)
    m.roi = (m.total_pnl / m.total_staked * 100) if m.total_staked else 0.0

    gross_profit = sum(p for p in pnls if p > 0)
    gross_loss = abs(sum(p for p in pnls if p < 0))
    m.profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float("inf")

    # Max drawdown: peak-to-trough of cumulative PnL series
    cum = 0.0
    peak = 0.0
    max_dd = 0.0
    for p in pnls:
        cum += p
        if cum > peak:
            peak = cum
        dd = peak - cum
        if dd > max_dd:
            max_dd = dd
    m.max_drawdown = max_dd

    # Sharpe: per-bet returns (pnl/stake), unannualized
    if len(pnls) >= 2:
        per_bet = [p / s for p, s in zip(pnls, stakes, strict=False)]
        mean_r = sum(per_bet) / len(per_bet)
        variance = sum((r - mean_r) ** 2 for r in per_bet) / (len(per_bet) - 1)
        std_r = math.sqrt(variance) if variance > 0 else 0.0
        m.sharpe = (mean_r / std_r) if std_r > 0 else 0.0

    return m


def _verdict(train: WindowMetrics, test: WindowMetrics) -> tuple[str, list[str]]:
    notes: list[str] = []

    if test.sample_size < _MIN_SAMPLE:
        notes.append(
            f"OOS sample too small ({test.sample_size} < {_MIN_SAMPLE}) — verdict unreliable"
        )

    oos_profitable = test.roi > 0
    oos_above_vig = test.win_rate > _VIG_BREAKEVEN
    is_profitable = train.roi > 0

    if oos_profitable and oos_above_vig and test.sample_size >= _MIN_SAMPLE:
        verdict = "EDGE_CONFIRMED"
    elif oos_profitable or oos_above_vig:
        verdict = "EDGE_MARGINAL"
    elif is_profitable and not oos_profitable:
        verdict = "EDGE_DEGRADED"
        notes.append("IS profitable but edge vanished OOS — possible overfitting")
    else:
        verdict = "NO_EDGE"

    if test.profit_factor > 1.0:
        notes.append(f"PF={test.profit_factor:.2f} — gross profit covers gross loss")
    if test.max_drawdown > 0:
        notes.append(f"Max drawdown OOS: {test.max_drawdown:.1f}u")

    return verdict, notes


def _fetch_bets_for_seasons(
    db: Session, setup_name: str, seasons: list[int]
) -> list[NbaQuantBet]:
    """Fetch settled bets for a setup filtered to specific seasons."""
    return (
        db.query(NbaQuantBet)
        .join(NbaSignal, NbaQuantBet.signal_id == NbaSignal.id)
        .join(NbaGame, NbaSignal.game_id == NbaGame.id)
        .filter(
            NbaSignal.setup_name == setup_name,
            NbaGame.season.in_(seasons),
            NbaQuantBet.status.in_([BetStatus.won, BetStatus.lost]),
        )
        .all()
    )


def run_oos_validation(
    db: Session,
    train_seasons: list[int] | None = None,
    test_seasons: list[int] | None = None,
    setups: list[str] | None = None,
) -> list[SetupOOSResult]:
    """
    Run out-of-sample validation for all setups (or a subset).

    Defaults:
        train_seasons = [2022, 2023]
        test_seasons  = [2024]
        setups        = all 4 setups
    """
    _train = train_seasons or [2022, 2023]
    _test = test_seasons or [2024]
    _setups = setups or [
        "HOME_DOG_V1",
        "REST_ADVANTAGE_V1",
        "BACK_TO_BACK_FADE_V1",
        "PACE_OVER_V1",
    ]

    results: list[SetupOOSResult] = []

    for setup_name in _setups:
        train_bets = _fetch_bets_for_seasons(db, setup_name, _train)
        test_bets = _fetch_bets_for_seasons(db, setup_name, _test)

        train_m = _compute_metrics(train_bets, _train)
        test_m = _compute_metrics(test_bets, _test)
        verdict, notes = _verdict(train_m, test_m)

        if not train_bets and not test_bets:
            notes.append("No settled bets found — HOME_DOG_V1 requires real ML odds")

        results.append(
            SetupOOSResult(
                setup_name=setup_name,
                train=train_m,
                test=test_m,
                verdict=verdict,
                notes=notes,
            )
        )

    return results
