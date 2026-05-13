"""Storage repository interfaces and backend factory."""

from __future__ import annotations

from typing import Protocol

from domains.crypto_coin.data.storage.models import (
    BotError,
    BotRun,
    EntryContext,
    EquityPoint,
    MarketSnapshot,
    OpenPositionState,
    RegimeRecord,
    ShadowTrade,
    SignalDecision,
    TradeResult,
)


class StorageRepository(Protocol):
    def init_schema(self) -> None: ...
    def close(self) -> None: ...
    def save_market_snapshot(self, snapshot: MarketSnapshot) -> int: ...
    def start_bot_run(self, run: BotRun) -> str: ...
    def finish_bot_run(
        self,
        run_id: str,
        status: str,
        stopped_at: object | None = None,
    ) -> None: ...
    def save_signal_decision(self, decision: SignalDecision) -> int: ...
    def save_bot_error(self, error: BotError) -> int: ...
    def save_entry_context(self, context: EntryContext) -> int: ...
    def save_trade_result(self, trade: TradeResult) -> int: ...
    def save_shadow_trade(self, trade: ShadowTrade) -> int: ...
    def close_shadow_trade(
        self,
        trade_id: int,
        *,
        exit_timestamp: object,
        exit_price: float,
        exit_reason: str,
        pnl_pct: float,
    ) -> None: ...
    def save_regime_record(self, regime: RegimeRecord) -> int: ...
    def save_equity_point(self, point: EquityPoint) -> int: ...
    def save_open_position_state(self, state: OpenPositionState) -> int: ...
    def load_open_position_state(
        self,
        symbol: str,
        strategy_id: str = "trend_following",
    ) -> dict | None: ...
    def clear_open_position_state(
        self,
        symbol: str,
        strategy_id: str = "trend_following",
    ) -> None: ...
    def fetch_recent_trades(
        self,
        limit: int = 50,
        symbol: str | None = None,
        strategy_id: str | None = None,
    ) -> list[dict]: ...
    def fetch_market_snapshots(
        self,
        symbol: str | None = None,
        timeframe: str | None = None,
        limit: int | None = None,
    ) -> list[dict]: ...
    def fetch_equity_curve(
        self,
        symbol: str | None = None,
        timeframe: str | None = None,
        limit: int | None = None,
    ) -> list[dict]: ...
    def fetch_regime_performance(
        self,
        symbol: str | None = None,
        timeframe: str | None = None,
    ) -> list[dict]: ...
    def fetch_mae_mfe_stats(
        self,
        symbol: str | None = None,
        strategy_id: str | None = None,
    ) -> dict: ...
    def fetch_confidence_performance(
        self,
        symbol: str | None = None,
        strategy_id: str | None = None,
    ) -> list[dict]: ...
    def fetch_signal_decision_summary(
        self,
        symbol: str | None = None,
        timeframe: str | None = None,
    ) -> dict: ...
    def fetch_signal_decisions(
        self,
        symbol: str | None = None,
        timeframe: str | None = None,
        limit: int | None = None,
    ) -> list[dict]: ...
    def fetch_strategy_version_performance(
        self,
        symbol: str | None = None,
        strategy_id: str | None = None,
    ) -> list[dict]: ...
    def fetch_strategy_version_regime_performance(
        self,
        symbol: str | None = None,
        timeframe: str | None = None,
        strategy_id: str | None = None,
    ) -> list[dict]: ...
    def fetch_shadow_trades(
        self,
        symbol: str | None = None,
        timeframe: str | None = None,
        limit: int | None = None,
    ) -> list[dict]: ...
    def fetch_open_shadow_trades(
        self,
        symbol: str | None = None,
        timeframe: str | None = None,
    ) -> list[dict]: ...
    def fetch_shadow_summary(
        self,
        symbol: str | None = None,
        timeframe: str | None = None,
    ) -> dict: ...
    def fetch_health(self) -> dict: ...


def create_storage(url: str) -> StorageRepository:
    """Create a storage backend from a URL.

    Supported now:
      - sqlite:///relative/or/absolute.db
      - sqlite:///:memory:

    PostgreSQL/TimescaleDB is intentionally reserved for the production adapter.
    """
    if not url:
        url = "sqlite:///data/bot_storage.sqlite3"

    if url.startswith("sqlite:///"):
        from domains.crypto_coin.data.storage.sqlite import SQLiteStorage

        return SQLiteStorage.from_url(url)

    if url.startswith(("postgresql://", "postgres://")):
        raise NotImplementedError(
            "PostgreSQL/TimescaleDB storage adapter is not implemented yet. "
            "Use sqlite:///data/bot_storage.sqlite3 for now."
        )

    raise ValueError(f"Unsupported storage URL: {url}")
