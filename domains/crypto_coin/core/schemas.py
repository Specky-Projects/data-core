"""
Contratos de dados do sistema.

Define os tipos que fluem entre todos os módulos:
  MarketTick, Signal, Trade, Position, Execution, RegimeState

Regra: nenhum módulo depende de outro para entender esses tipos.
Qualquer componente novo que precisar falar com o sistema usa esses schemas.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class MarketTick:
    """Um candle OHLCV recebido da exchange."""
    symbol:    str
    timeframe: str
    timestamp: datetime
    open:   float
    high:   float
    low:    float
    close:  float
    volume: float


@dataclass
class Signal:
    """Sinal gerado por uma estratégia."""
    strategy_id: str
    symbol:      str
    timestamp:   datetime
    action:      str          # "BUY" | "SELL" | "HOLD" | "STOP_LOSS" | "TAKE_PROFIT"
    confidence:  int          # 0-100
    price:       float
    metadata:    dict = field(default_factory=dict)   # indicadores, regime, etc.


@dataclass
class Position:
    """Posição aberta."""
    symbol:      str
    strategy_id: str
    entry_price: float
    amount:      float
    entry_time:  datetime
    stop_price:  float | None = None
    tp_price:    float | None = None


@dataclass
class Trade:
    """Trade fechado (par buy→sell)."""
    symbol:      str
    strategy_id: str
    side:        str          # "BUY" | "SELL"
    price:       float
    amount:      float
    timestamp:   datetime
    pnl:         float | None = None
    pnl_pct:     float | None = None
    signal:      str | None   = None
    confidence:  int | None   = None
    paper:       bool = True


@dataclass
class Execution:
    """Resultado de uma ordem executada na exchange."""
    order_id:  str
    symbol:    str
    side:      str
    price:     float
    amount:    float
    cost:      float
    timestamp: datetime
    slippage:  float = 0.0
    fee:       float = 0.0


@dataclass
class RegimeState:
    """Estado atual do regime de mercado."""
    symbol:     str
    timeframe:  str
    timestamp:  datetime
    regime:     str           # "trending_up" | "trending_down" | "ranging" | "unknown"
    confidence: int           # 0-100
    atr:        float | None = None
    atr_pct:    float | None = None
    hv:         float | None = None
    adx:        float | None = None
    volume_ratio: float | None = None
    breakout_score: float = 0.0


@dataclass
class Event:
    """Envelope genérico para o event bus."""
    type:      str
    timestamp: datetime
    payload:   Any = None
    source:    str = ""
