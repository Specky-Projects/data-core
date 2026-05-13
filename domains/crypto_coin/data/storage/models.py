"""Data contracts for durable bot storage."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


JsonDict = dict[str, Any]


@dataclass(frozen=True)
class MarketSnapshot:
    symbol: str
    timeframe: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    indicators: JsonDict = field(default_factory=dict)


@dataclass(frozen=True)
class EntryContext:
    symbol: str
    timeframe: str
    timestamp: datetime
    strategy_id: str
    signal: str
    price: float
    confidence: int
    strategy_version: str = "v1.0"
    regime: Optional[str] = None
    mtf_bias: Optional[str] = None
    strategy_return_pct: Optional[float] = None
    context: JsonDict = field(default_factory=dict)


@dataclass(frozen=True)
class TradeResult:
    symbol: str
    strategy_id: str
    side: str
    timestamp: datetime
    price: float
    amount: float
    strategy_version: str = "v1.0"
    cost: Optional[float] = None
    order_id: Optional[str] = None
    signal: Optional[str] = None
    confidence: Optional[int] = None
    pnl: Optional[float] = None
    pnl_pct: Optional[float] = None
    slippage: Optional[float] = None
    mae: Optional[float] = None
    mfe: Optional[float] = None
    fee: Optional[float] = None
    loss_type: Optional[str] = None
    paper: bool = True
    details: JsonDict = field(default_factory=dict)


@dataclass(frozen=True)
class RegimeRecord:
    symbol: str
    timeframe: str
    timestamp: datetime
    regime: str
    confidence: int
    atr: Optional[float] = None
    atr_pct: Optional[float] = None
    hv: Optional[float] = None
    adx: Optional[float] = None
    volume_ratio: Optional[float] = None
    breakout_score: Optional[float] = None


@dataclass(frozen=True)
class EquityPoint:
    symbol: str
    timeframe: str
    timestamp: datetime
    equity: float
    quote_balance: float
    base_amount: float = 0.0
    mark_price: Optional[float] = None
    realized_pnl: Optional[float] = None
    paper: bool = True


@dataclass(frozen=True)
class OpenPositionState:
    symbol: str
    strategy_id: str
    timestamp: datetime
    in_position: bool
    buy_price: Optional[float] = None
    amount: float = 0.0
    entry_confidence: int = 0
    position_low: Optional[float] = None
    position_high: Optional[float] = None
    trailing_stop_price: Optional[float] = None
    trailing_highest_price: Optional[float] = None
    trailing_activated: bool = False
    quote_balance: Optional[float] = None
    base_amount: Optional[float] = None
    paper: bool = True
    metadata: JsonDict = field(default_factory=dict)


@dataclass(frozen=True)
class BotRun:
    run_id: str
    started_at: datetime
    status: str = "running"
    stopped_at: Optional[datetime] = None
    symbol: Optional[str] = None
    timeframe: Optional[str] = None
    paper: bool = True
    metadata: JsonDict = field(default_factory=dict)


@dataclass(frozen=True)
class SignalDecision:
    run_id: str
    symbol: str
    timeframe: str
    timestamp: datetime
    strategy_id: str
    signal: str
    accepted: bool
    reason: str
    price: float
    confidence: int
    strategy_version: str = "v1.0"
    regime: Optional[str] = None
    mtf_bias: Optional[str] = None
    strategy_return_pct: Optional[float] = None
    setup_score: Optional[float] = None
    setup_quality: Optional[str] = None
    context: JsonDict = field(default_factory=dict)


@dataclass(frozen=True)
class ShadowTrade:
    run_id: str
    symbol: str
    timeframe: str
    strategy_id: str
    strategy_version: str
    entry_timestamp: datetime
    entry_price: float
    stop_price: float
    take_profit_price: float
    signal: str
    confidence: int
    setup_score: Optional[float] = None
    setup_quality: Optional[str] = None
    regime: Optional[str] = None
    mtf_bias: Optional[str] = None
    status: str = "open"
    exit_timestamp: Optional[datetime] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[str] = None
    pnl_pct: Optional[float] = None
    metadata: JsonDict = field(default_factory=dict)


@dataclass(frozen=True)
class BotError:
    run_id: str
    timestamp: datetime
    source: str
    message: str
    error_type: Optional[str] = None
    traceback: Optional[str] = None
    context: JsonDict = field(default_factory=dict)
