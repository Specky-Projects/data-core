"""Data contracts for durable bot storage."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

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
    regime: str | None = None
    mtf_bias: str | None = None
    strategy_return_pct: float | None = None
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
    cost: float | None = None
    order_id: str | None = None
    signal: str | None = None
    confidence: int | None = None
    pnl: float | None = None
    pnl_pct: float | None = None
    slippage: float | None = None
    mae: float | None = None
    mfe: float | None = None
    fee: float | None = None
    loss_type: str | None = None
    paper: bool = True
    details: JsonDict = field(default_factory=dict)


@dataclass(frozen=True)
class RegimeRecord:
    symbol: str
    timeframe: str
    timestamp: datetime
    regime: str
    confidence: int
    atr: float | None = None
    atr_pct: float | None = None
    hv: float | None = None
    adx: float | None = None
    volume_ratio: float | None = None
    breakout_score: float | None = None


@dataclass(frozen=True)
class EquityPoint:
    symbol: str
    timeframe: str
    timestamp: datetime
    equity: float
    quote_balance: float
    base_amount: float = 0.0
    mark_price: float | None = None
    realized_pnl: float | None = None
    paper: bool = True


@dataclass(frozen=True)
class OpenPositionState:
    symbol: str
    strategy_id: str
    timestamp: datetime
    in_position: bool
    buy_price: float | None = None
    amount: float = 0.0
    entry_confidence: int = 0
    position_low: float | None = None
    position_high: float | None = None
    trailing_stop_price: float | None = None
    trailing_highest_price: float | None = None
    trailing_activated: bool = False
    quote_balance: float | None = None
    base_amount: float | None = None
    paper: bool = True
    metadata: JsonDict = field(default_factory=dict)


@dataclass(frozen=True)
class BotRun:
    run_id: str
    started_at: datetime
    status: str = "running"
    stopped_at: datetime | None = None
    symbol: str | None = None
    timeframe: str | None = None
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
    regime: str | None = None
    mtf_bias: str | None = None
    strategy_return_pct: float | None = None
    setup_score: float | None = None
    setup_quality: str | None = None
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
    setup_score: float | None = None
    setup_quality: str | None = None
    regime: str | None = None
    mtf_bias: str | None = None
    status: str = "open"
    exit_timestamp: datetime | None = None
    exit_price: float | None = None
    exit_reason: str | None = None
    pnl_pct: float | None = None
    metadata: JsonDict = field(default_factory=dict)


@dataclass(frozen=True)
class BotError:
    run_id: str
    timestamp: datetime
    source: str
    message: str
    error_type: str | None = None
    traceback: str | None = None
    context: JsonDict = field(default_factory=dict)
