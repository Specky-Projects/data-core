"""
Canonical enums shared by NBA and WNBA quant modules.

Imported by:
  - app.modules.nba.quant.models (re-exported for backward compat)
  - app.modules.basketball.wnba.models
"""
import enum


class GameStatus(str, enum.Enum):
    scheduled = "scheduled"
    live = "live"
    final = "final"


class MarketType(str, enum.Enum):
    moneyline = "moneyline"
    spread = "spread"
    totals = "totals"


class SignalDirection(str, enum.Enum):
    home = "home"
    away = "away"
    over = "over"
    under = "under"


class BetStatus(str, enum.Enum):
    pending = "pending"
    won = "won"
    lost = "lost"
    void = "void"


class EdgeClassification(str, enum.Enum):
    profitable = "profitable"
    neutral = "neutral"
    losing = "losing"
