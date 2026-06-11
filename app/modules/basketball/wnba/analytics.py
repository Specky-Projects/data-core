"""
WNBA analytics engine.

Uses shared base helpers (drawdown, classify, dataclasses) from basketball.shared.analytics_base.
Queries WNBA-specific ORM models.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.modules.basketball.shared.analytics_base import (
    GlobalAnalytics,
    SetupAnalytics,
    classify,
    drawdown,
)
from app.modules.basketball.shared.enums import BetStatus, EdgeClassification
from app.modules.basketball.wnba.models import WnbaEdgeRegistry, WnbaQuantBet, WnbaSignal


def setup_analytics(db: Session, setup_name: str) -> SetupAnalytics:
    bets = (
        db.query(WnbaQuantBet)
        .join(WnbaSignal, WnbaQuantBet.signal_id == WnbaSignal.id)
        .filter(WnbaSignal.setup_name == setup_name)
        .order_by(WnbaQuantBet.created_at)
        .all()
    )

    wins = [b for b in bets if b.status == BetStatus.won]
    losses = [b for b in bets if b.status == BetStatus.lost]
    pending = [b for b in bets if b.status == BetStatus.pending]
    void = [b for b in bets if b.status == BetStatus.void]
    settled = wins + losses

    total_staked = len(settled) * 1.0
    pnl_vals = [float(b.pnl or 0) for b in settled]
    total_pnl = sum(pnl_vals)

    roi = round(total_pnl / total_staked * 100, 2) if total_staked else 0.0
    win_rate = round(len(wins) / len(settled) * 100, 2) if settled else 0.0

    gross_profit = sum(float(b.pnl or 0) for b in wins)
    gross_loss = abs(sum(float(b.pnl or 0) for b in losses))
    profit_factor = round(gross_profit / gross_loss, 3) if gross_loss > 0 else 0.0

    avg_win = gross_profit / len(wins) if wins else 0.0
    avg_loss = gross_loss / len(losses) if losses else 0.0
    wr = win_rate / 100
    expectancy = round(wr * avg_win - (1 - wr) * avg_loss, 4) if settled else 0.0

    dd = drawdown(pnl_vals)
    cls = classify(roi, len(settled))

    return SetupAnalytics(
        setup_name=setup_name,
        total_bets=len(bets),
        wins=len(wins),
        losses=len(losses),
        pending=len(pending),
        void=len(void),
        roi=roi,
        yield_pct=roi,
        win_rate=win_rate,
        profit_factor=profit_factor,
        expectancy=expectancy,
        max_drawdown=dd,
        classification=cls.value,
    )


def global_analytics(db: Session) -> GlobalAnalytics:
    all_bets = (
        db.query(WnbaQuantBet)
        .join(WnbaSignal, WnbaQuantBet.signal_id == WnbaSignal.id)
        .order_by(WnbaQuantBet.created_at)
        .all()
    )

    wins = sum(1 for b in all_bets if b.status == BetStatus.won)
    losses = sum(1 for b in all_bets if b.status == BetStatus.lost)
    pending = sum(1 for b in all_bets if b.status == BetStatus.pending)
    void = sum(1 for b in all_bets if b.status == BetStatus.void)
    settled = wins + losses
    total_staked = settled * 1.0
    total_pnl = sum(
        float(b.pnl or 0)
        for b in all_bets
        if b.status in (BetStatus.won, BetStatus.lost)
    )
    roi = round(total_pnl / total_staked * 100, 2) if total_staked else 0.0
    win_rate = round(wins / settled * 100, 2) if settled else 0.0

    total_signals = db.query(WnbaSignal).count()
    setups = db.query(WnbaSignal.setup_name).group_by(WnbaSignal.setup_name).all()
    setup_list = sorted(
        [setup_analytics(db, s[0]) for s in setups],
        key=lambda s: s.roi,
        reverse=True,
    )

    return GlobalAnalytics(
        total_signals=total_signals,
        total_bets=len(all_bets),
        wins=wins,
        losses=losses,
        pending=pending,
        void=void,
        roi=roi,
        pnl=round(total_pnl, 4),
        win_rate=win_rate,
        setups=setup_list,
    )


def refresh_edge_registry(db: Session) -> list[WnbaEdgeRegistry]:
    """Recompute and upsert WNBA edge registry for all setups."""
    from app.modules.basketball.wnba.metrics import wnba_q_setup_roi, wnba_q_setup_win_rate

    setups = db.query(WnbaSignal.setup_name).group_by(WnbaSignal.setup_name).all()
    records = []

    for (setup_name,) in setups:
        sa = setup_analytics(db, setup_name)
        cls = EdgeClassification(sa.classification)

        entry = (
            db.query(WnbaEdgeRegistry)
            .filter(WnbaEdgeRegistry.setup_name == setup_name)
            .first()
        )
        if not entry:
            entry = WnbaEdgeRegistry(setup_name=setup_name)
            db.add(entry)

        entry.total_bets = sa.total_bets
        entry.wins = sa.wins
        entry.losses = sa.losses
        entry.pending = sa.pending
        entry.void = sa.void
        entry.roi = sa.roi
        entry.yield_pct = sa.yield_pct
        entry.win_rate = sa.win_rate
        entry.profit_factor = sa.profit_factor
        entry.expectancy = sa.expectancy
        entry.max_drawdown = sa.max_drawdown
        entry.classification = cls

        wnba_q_setup_roi.labels(setup=setup_name).set(sa.roi)
        wnba_q_setup_win_rate.labels(setup=setup_name).set(sa.win_rate)

        records.append(entry)

    db.commit()
    return records
