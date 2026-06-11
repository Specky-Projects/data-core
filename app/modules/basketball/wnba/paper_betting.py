"""
WNBA paper bet settlement.

Uses shared _pnl and determine_result from basketball.shared.settlement.
"""
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.modules.basketball.shared.enums import BetStatus, GameStatus
from app.modules.basketball.shared.settlement import determine_result, pnl
from app.modules.basketball.wnba.models import WnbaGame, WnbaQuantBet, WnbaSignal


def settle_game(db: Session, game_id: str) -> int:
    """Settle all pending WNBA bets for a finished game. Returns number settled."""
    from app.modules.basketball.wnba.metrics import wnba_q_bets_settled_total

    game = db.query(WnbaGame).filter(WnbaGame.id == game_id).first()
    if not game or game.status != GameStatus.final:
        return 0

    bets = (
        db.query(WnbaQuantBet)
        .join(WnbaSignal, WnbaQuantBet.signal_id == WnbaSignal.id)
        .filter(WnbaSignal.game_id == game_id, WnbaQuantBet.status == BetStatus.pending)
        .all()
    )

    settled = 0
    for bet in bets:
        result = determine_result(game, bet.signal)
        if result is None:
            continue
        odd = float(bet.signal.odd)
        bet.status = result
        bet.settled_at = datetime.now(timezone.utc)
        bet.pnl = pnl(odd, float(bet.stake), result == BetStatus.won)
        if result == BetStatus.void:
            bet.pnl = 0.0
        settled += 1
        wnba_q_bets_settled_total.labels(
            setup=bet.signal.setup_name, result=result.value
        ).inc()

    db.commit()

    try:
        from app.modules.basketball.wnba.telegram_alerts import send_settlement_alert
        for bet in bets:
            if bet.status != BetStatus.pending:
                send_settlement_alert(bet.signal, bet, game, db=db)
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("WNBA settlement Telegram alert failed: %s", exc)

    return settled


def settle_all_pending(db: Session) -> int:
    """Settle all pending WNBA bets for finished games."""
    pending_game_ids = (
        db.query(WnbaSignal.game_id)
        .join(WnbaQuantBet, WnbaSignal.id == WnbaQuantBet.signal_id)
        .join(WnbaGame, WnbaSignal.game_id == WnbaGame.id)
        .filter(WnbaQuantBet.status == BetStatus.pending, WnbaGame.status == GameStatus.final)
        .distinct()
        .all()
    )
    total = 0
    for (game_id,) in pending_game_ids:
        total += settle_game(db, str(game_id))
    return total
