"""SQLite storage backend for bot memory."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

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


class SQLiteStorage:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        if str(self.path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")

    @classmethod
    def from_url(cls, url: str) -> "SQLiteStorage":
        path = url.removeprefix("sqlite:///")
        if path == ":memory:":
            return cls(":memory:")
        return cls(Path(path))

    def init_schema(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS market_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                open REAL NOT NULL,
                high REAL NOT NULL,
                low REAL NOT NULL,
                close REAL NOT NULL,
                volume REAL NOT NULL,
                indicators_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(symbol, timeframe, timestamp)
            );

            CREATE TABLE IF NOT EXISTS entry_contexts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                strategy_id TEXT NOT NULL,
                strategy_version TEXT NOT NULL DEFAULT 'v1.0',
                signal TEXT NOT NULL,
                price REAL NOT NULL,
                confidence INTEGER NOT NULL,
                regime TEXT,
                mtf_bias TEXT,
                strategy_return_pct REAL,
                context_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS trade_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                strategy_id TEXT NOT NULL,
                strategy_version TEXT NOT NULL DEFAULT 'v1.0',
                side TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                price REAL NOT NULL,
                amount REAL NOT NULL,
                cost REAL,
                order_id TEXT,
                signal TEXT,
                confidence INTEGER,
                pnl REAL,
                pnl_pct REAL,
                slippage REAL,
                mae REAL,
                mfe REAL,
                fee REAL,
                loss_type TEXT,
                paper INTEGER NOT NULL,
                details_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS regime_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                regime TEXT NOT NULL,
                confidence INTEGER NOT NULL,
                atr REAL,
                atr_pct REAL,
                hv REAL,
                adx REAL,
                volume_ratio REAL,
                breakout_score REAL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(symbol, timeframe, timestamp)
            );

            CREATE TABLE IF NOT EXISTS equity_curve (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                equity REAL NOT NULL,
                quote_balance REAL NOT NULL,
                base_amount REAL NOT NULL DEFAULT 0,
                mark_price REAL,
                realized_pnl REAL,
                paper INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS open_position_state (
                symbol TEXT NOT NULL,
                strategy_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                in_position INTEGER NOT NULL,
                buy_price REAL,
                amount REAL NOT NULL DEFAULT 0,
                entry_confidence INTEGER NOT NULL DEFAULT 0,
                position_low REAL,
                position_high REAL,
                trailing_stop_price REAL,
                trailing_highest_price REAL,
                trailing_activated INTEGER NOT NULL DEFAULT 0,
                quote_balance REAL,
                base_amount REAL,
                paper INTEGER NOT NULL,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY(symbol, strategy_id)
            );

            CREATE TABLE IF NOT EXISTS bot_runs (
                run_id TEXT PRIMARY KEY,
                started_at TEXT NOT NULL,
                stopped_at TEXT,
                status TEXT NOT NULL,
                symbol TEXT,
                timeframe TEXT,
                paper INTEGER NOT NULL,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS signal_decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                strategy_id TEXT NOT NULL,
                strategy_version TEXT NOT NULL DEFAULT 'v1.0',
                signal TEXT NOT NULL,
                accepted INTEGER NOT NULL,
                reason TEXT NOT NULL,
                price REAL NOT NULL,
                confidence INTEGER NOT NULL,
                regime TEXT,
                mtf_bias TEXT,
                strategy_return_pct REAL,
                setup_score REAL,
                setup_quality TEXT,
                context_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS shadow_trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                strategy_id TEXT NOT NULL,
                strategy_version TEXT NOT NULL DEFAULT 'v1.0',
                entry_timestamp TEXT NOT NULL,
                entry_price REAL NOT NULL,
                stop_price REAL NOT NULL,
                take_profit_price REAL NOT NULL,
                signal TEXT NOT NULL,
                confidence INTEGER NOT NULL,
                setup_score REAL,
                setup_quality TEXT,
                regime TEXT,
                mtf_bias TEXT,
                status TEXT NOT NULL DEFAULT 'open',
                exit_timestamp TEXT,
                exit_price REAL,
                exit_reason TEXT,
                pnl_pct REAL,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS bot_errors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                source TEXT NOT NULL,
                message TEXT NOT NULL,
                error_type TEXT,
                traceback TEXT,
                context_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_market_snapshots_lookup
                ON market_snapshots(symbol, timeframe, timestamp);
            CREATE INDEX IF NOT EXISTS idx_trade_results_lookup
                ON trade_results(symbol, strategy_id, timestamp);
            CREATE INDEX IF NOT EXISTS idx_regime_history_lookup
                ON regime_history(symbol, timeframe, timestamp);
            CREATE INDEX IF NOT EXISTS idx_equity_curve_lookup
                ON equity_curve(symbol, timeframe, timestamp);
            CREATE INDEX IF NOT EXISTS idx_open_position_state_lookup
                ON open_position_state(symbol, strategy_id);
            CREATE INDEX IF NOT EXISTS idx_signal_decisions_lookup
                ON signal_decisions(symbol, timeframe, timestamp);
            CREATE INDEX IF NOT EXISTS idx_shadow_trades_lookup
                ON shadow_trades(symbol, timeframe, status, entry_timestamp);
            CREATE INDEX IF NOT EXISTS idx_bot_errors_lookup
                ON bot_errors(run_id, timestamp);
            """
        )
        self._ensure_schema_updates()
        self.conn.commit()

    def _ensure_schema_updates(self) -> None:
        self._ensure_column("entry_contexts", "strategy_version", "strategy_version TEXT NOT NULL DEFAULT 'v1.0'")
        self._ensure_column("trade_results", "strategy_version", "strategy_version TEXT NOT NULL DEFAULT 'v1.0'")
        self._ensure_column("trade_results", "loss_type", "loss_type TEXT")
        self._ensure_column("signal_decisions", "strategy_version", "strategy_version TEXT NOT NULL DEFAULT 'v1.0'")
        self._ensure_column("signal_decisions", "setup_score", "setup_score REAL")
        self._ensure_column("signal_decisions", "setup_quality", "setup_quality TEXT")

    def _ensure_column(self, table: str, column: str, ddl: str) -> None:
        rows = self.conn.execute(f"PRAGMA table_info({table})").fetchall()
        if column not in {row["name"] for row in rows}:
            self.conn.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")

    def close(self) -> None:
        self.conn.close()

    def save_market_snapshot(self, snapshot: MarketSnapshot) -> int:
        cur = self.conn.execute(
            """
            INSERT OR IGNORE INTO market_snapshots (
                symbol, timeframe, timestamp, open, high, low, close, volume,
                indicators_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot.symbol,
                snapshot.timeframe,
                _iso(snapshot.timestamp),
                snapshot.open,
                snapshot.high,
                snapshot.low,
                snapshot.close,
                snapshot.volume,
                _json(snapshot.indicators),
            ),
        )
        self.conn.commit()
        return int(cur.lastrowid or 0)

    def start_bot_run(self, run: BotRun) -> str:
        self.conn.execute(
            """
            INSERT INTO bot_runs (
                run_id, started_at, stopped_at, status, symbol, timeframe, paper,
                metadata_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(run_id) DO UPDATE SET
                stopped_at = excluded.stopped_at,
                status = excluded.status,
                symbol = excluded.symbol,
                timeframe = excluded.timeframe,
                paper = excluded.paper,
                metadata_json = excluded.metadata_json,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                run.run_id,
                _iso(run.started_at),
                _iso(run.stopped_at) if run.stopped_at else None,
                run.status,
                run.symbol,
                run.timeframe,
                1 if run.paper else 0,
                _json(run.metadata),
            ),
        )
        self.conn.commit()
        return run.run_id

    def finish_bot_run(
        self,
        run_id: str,
        status: str,
        stopped_at: datetime | None = None,
    ) -> None:
        self.conn.execute(
            """
            UPDATE bot_runs
            SET status = ?, stopped_at = ?, updated_at = CURRENT_TIMESTAMP
            WHERE run_id = ?
            """,
            (status, _iso(stopped_at or datetime.utcnow()), run_id),
        )
        self.conn.commit()

    def save_signal_decision(self, decision: SignalDecision) -> int:
        cur = self.conn.execute(
            """
            INSERT INTO signal_decisions (
                run_id, symbol, timeframe, timestamp, strategy_id, strategy_version, signal,
                accepted, reason, price, confidence, regime, mtf_bias,
                strategy_return_pct, setup_score, setup_quality, context_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                decision.run_id,
                decision.symbol,
                decision.timeframe,
                _iso(decision.timestamp),
                decision.strategy_id,
                decision.strategy_version,
                decision.signal,
                1 if decision.accepted else 0,
                decision.reason,
                decision.price,
                decision.confidence,
                decision.regime,
                decision.mtf_bias,
                decision.strategy_return_pct,
                decision.setup_score,
                decision.setup_quality,
                _json(decision.context),
            ),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def save_bot_error(self, error: BotError) -> int:
        cur = self.conn.execute(
            """
            INSERT INTO bot_errors (
                run_id, timestamp, source, message, error_type, traceback,
                context_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                error.run_id,
                _iso(error.timestamp),
                error.source,
                error.message,
                error.error_type,
                error.traceback,
                _json(error.context),
            ),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def save_entry_context(self, context: EntryContext) -> int:
        cur = self.conn.execute(
            """
            INSERT INTO entry_contexts (
                symbol, timeframe, timestamp, strategy_id, strategy_version, signal, price,
                confidence, regime, mtf_bias, strategy_return_pct, context_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                context.symbol,
                context.timeframe,
                _iso(context.timestamp),
                context.strategy_id,
                context.strategy_version,
                context.signal,
                context.price,
                context.confidence,
                context.regime,
                context.mtf_bias,
                context.strategy_return_pct,
                _json(context.context),
            ),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def save_trade_result(self, trade: TradeResult) -> int:
        cur = self.conn.execute(
            """
            INSERT INTO trade_results (
                symbol, strategy_id, strategy_version, side, timestamp, price, amount, cost,
                order_id, signal, confidence, pnl, pnl_pct, slippage, mae, mfe,
                fee, loss_type, paper, details_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                trade.symbol,
                trade.strategy_id,
                trade.strategy_version,
                trade.side,
                _iso(trade.timestamp),
                trade.price,
                trade.amount,
                trade.cost,
                trade.order_id,
                trade.signal,
                trade.confidence,
                trade.pnl,
                trade.pnl_pct,
                trade.slippage,
                trade.mae,
                trade.mfe,
                trade.fee,
                trade.loss_type,
                1 if trade.paper else 0,
                _json(trade.details),
            ),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def save_shadow_trade(self, trade: ShadowTrade) -> int:
        cur = self.conn.execute(
            """
            INSERT INTO shadow_trades (
                run_id, symbol, timeframe, strategy_id, strategy_version,
                entry_timestamp, entry_price, stop_price, take_profit_price,
                signal, confidence, setup_score, setup_quality, regime, mtf_bias,
                status, exit_timestamp, exit_price, exit_reason, pnl_pct,
                metadata_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                trade.run_id,
                trade.symbol,
                trade.timeframe,
                trade.strategy_id,
                trade.strategy_version,
                _iso(trade.entry_timestamp),
                trade.entry_price,
                trade.stop_price,
                trade.take_profit_price,
                trade.signal,
                trade.confidence,
                trade.setup_score,
                trade.setup_quality,
                trade.regime,
                trade.mtf_bias,
                trade.status,
                _iso(trade.exit_timestamp) if trade.exit_timestamp else None,
                trade.exit_price,
                trade.exit_reason,
                trade.pnl_pct,
                _json(trade.metadata),
            ),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def close_shadow_trade(
        self,
        trade_id: int,
        *,
        exit_timestamp: datetime,
        exit_price: float,
        exit_reason: str,
        pnl_pct: float,
    ) -> None:
        self.conn.execute(
            """
            UPDATE shadow_trades
            SET status = 'closed',
                exit_timestamp = ?,
                exit_price = ?,
                exit_reason = ?,
                pnl_pct = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND status = 'open'
            """,
            (_iso(exit_timestamp), exit_price, exit_reason, pnl_pct, trade_id),
        )
        self.conn.commit()

    def save_regime_record(self, regime: RegimeRecord) -> int:
        cur = self.conn.execute(
            """
            INSERT OR IGNORE INTO regime_history (
                symbol, timeframe, timestamp, regime, confidence, atr, atr_pct,
                hv, adx, volume_ratio, breakout_score
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                regime.symbol,
                regime.timeframe,
                _iso(regime.timestamp),
                regime.regime,
                regime.confidence,
                regime.atr,
                regime.atr_pct,
                regime.hv,
                regime.adx,
                regime.volume_ratio,
                regime.breakout_score,
            ),
        )
        self.conn.commit()
        return int(cur.lastrowid or 0)

    def save_equity_point(self, point: EquityPoint) -> int:
        cur = self.conn.execute(
            """
            INSERT INTO equity_curve (
                symbol, timeframe, timestamp, equity, quote_balance,
                base_amount, mark_price, realized_pnl, paper
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                point.symbol,
                point.timeframe,
                _iso(point.timestamp),
                point.equity,
                point.quote_balance,
                point.base_amount,
                point.mark_price,
                point.realized_pnl,
                1 if point.paper else 0,
            ),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def save_open_position_state(self, state: OpenPositionState) -> int:
        cur = self.conn.execute(
            """
            INSERT INTO open_position_state (
                symbol, strategy_id, timestamp, in_position, buy_price, amount,
                entry_confidence, position_low, position_high, trailing_stop_price,
                trailing_highest_price, trailing_activated, quote_balance,
                base_amount, paper, metadata_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(symbol, strategy_id) DO UPDATE SET
                timestamp = excluded.timestamp,
                in_position = excluded.in_position,
                buy_price = excluded.buy_price,
                amount = excluded.amount,
                entry_confidence = excluded.entry_confidence,
                position_low = excluded.position_low,
                position_high = excluded.position_high,
                trailing_stop_price = excluded.trailing_stop_price,
                trailing_highest_price = excluded.trailing_highest_price,
                trailing_activated = excluded.trailing_activated,
                quote_balance = excluded.quote_balance,
                base_amount = excluded.base_amount,
                paper = excluded.paper,
                metadata_json = excluded.metadata_json,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                state.symbol,
                state.strategy_id,
                _iso(state.timestamp),
                1 if state.in_position else 0,
                state.buy_price,
                state.amount,
                state.entry_confidence,
                state.position_low,
                state.position_high,
                state.trailing_stop_price,
                state.trailing_highest_price,
                1 if state.trailing_activated else 0,
                state.quote_balance,
                state.base_amount,
                1 if state.paper else 0,
                _json(state.metadata),
            ),
        )
        self.conn.commit()
        return int(cur.lastrowid or 0)

    def load_open_position_state(
        self,
        symbol: str,
        strategy_id: str = "trend_following",
    ) -> dict | None:
        row = self.conn.execute(
            """
            SELECT * FROM open_position_state
            WHERE symbol = ? AND strategy_id = ?
            """,
            (symbol, strategy_id),
        ).fetchone()
        if row is None:
            return None
        data = _row_to_dict(row)
        data["in_position"] = bool(data.get("in_position"))
        data["trailing_activated"] = bool(data.get("trailing_activated"))
        data["paper"] = bool(data.get("paper"))
        return data

    def clear_open_position_state(
        self,
        symbol: str,
        strategy_id: str = "trend_following",
    ) -> None:
        self.conn.execute(
            "DELETE FROM open_position_state WHERE symbol = ? AND strategy_id = ?",
            (symbol, strategy_id),
        )
        self.conn.commit()

    def fetch_recent_trades(
        self,
        limit: int = 50,
        symbol: str | None = None,
        strategy_id: str | None = None,
    ) -> list[dict]:
        where = []
        params: list[Any] = []
        if symbol:
            where.append("symbol = ?")
            params.append(symbol)
        if strategy_id:
            where.append("strategy_id = ?")
            params.append(strategy_id)

        sql = "SELECT * FROM trade_results"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY timestamp DESC, id DESC LIMIT ?"
        params.append(max(1, int(limit)))
        return [_row_to_dict(row) for row in self.conn.execute(sql, params).fetchall()]

    def fetch_market_snapshots(
        self,
        symbol: str | None = None,
        timeframe: str | None = None,
        limit: int | None = None,
    ) -> list[dict]:
        where = []
        params: list[Any] = []
        if symbol:
            where.append("symbol = ?")
            params.append(symbol)
        if timeframe:
            where.append("timeframe = ?")
            params.append(timeframe)

        sql = "SELECT * FROM market_snapshots"
        if where:
            sql += " WHERE " + " AND ".join(where)
        if limit is not None:
            sql += " ORDER BY timestamp DESC, id DESC LIMIT ?"
            params.append(max(1, int(limit)))
            rows = self.conn.execute(sql, params).fetchall()
            return [_row_to_dict(row) for row in reversed(rows)]
        sql += " ORDER BY timestamp ASC, id ASC"
        return [_row_to_dict(row) for row in self.conn.execute(sql, params).fetchall()]

    def fetch_equity_curve(
        self,
        symbol: str | None = None,
        timeframe: str | None = None,
        limit: int | None = None,
    ) -> list[dict]:
        where = []
        params: list[Any] = []
        if symbol:
            where.append("symbol = ?")
            params.append(symbol)
        if timeframe:
            where.append("timeframe = ?")
            params.append(timeframe)

        sql = "SELECT * FROM equity_curve"
        if where:
            sql += " WHERE " + " AND ".join(where)
        if limit is not None:
            sql += " ORDER BY timestamp DESC, id DESC LIMIT ?"
            params.append(max(1, int(limit)))
            rows = self.conn.execute(sql, params).fetchall()
            return [_row_to_dict(row) for row in reversed(rows)]

        sql += " ORDER BY timestamp ASC, id ASC"
        return [_row_to_dict(row) for row in self.conn.execute(sql, params).fetchall()]

    def fetch_regime_performance(
        self,
        symbol: str | None = None,
        timeframe: str | None = None,
    ) -> list[dict]:
        where = ["tr.pnl IS NOT NULL"]
        where_params: list[Any] = []
        if symbol:
            where.append("tr.symbol = ?")
            where_params.append(symbol)

        timeframe_filter = ""
        subquery_params: list[Any] = []
        if timeframe:
            timeframe_filter = " AND ec.timeframe = ?"
            subquery_params.append(timeframe)

        sql = f"""
            SELECT
                COALESCE(regime, 'unknown') AS regime,
                COUNT(*) AS total_trades,
                SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) AS wins,
                SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) AS losses,
                SUM(pnl) AS net_pnl,
                AVG(pnl) AS avg_pnl,
                AVG(pnl_pct) AS avg_pnl_pct,
                AVG(mae) AS avg_mae,
                AVG(mfe) AS avg_mfe
            FROM (
                SELECT
                    tr.*,
                    (
                        SELECT ec.regime
                        FROM entry_contexts ec
                        WHERE ec.symbol = tr.symbol
                          AND ec.strategy_id = tr.strategy_id
                          AND ec.timestamp <= tr.timestamp
                          {timeframe_filter}
                        ORDER BY ec.timestamp DESC, ec.id DESC
                        LIMIT 1
                    ) AS regime
                FROM trade_results tr
                WHERE {" AND ".join(where)}
            )
            GROUP BY COALESCE(regime, 'unknown')
            ORDER BY net_pnl DESC
        """
        params = subquery_params + where_params
        rows = self.conn.execute(sql, params).fetchall()
        out = []
        for row in rows:
            item = _row_to_dict(row)
            total = item.get("total_trades") or 0
            wins = item.get("wins") or 0
            item["win_rate"] = round((wins / total) * 100, 2) if total else 0.0
            out.append(item)
        return out

    def fetch_mae_mfe_stats(
        self,
        symbol: str | None = None,
        strategy_id: str | None = None,
    ) -> dict:
        where = ["pnl IS NOT NULL"]
        params: list[Any] = []
        if symbol:
            where.append("symbol = ?")
            params.append(symbol)
        if strategy_id:
            where.append("strategy_id = ?")
            params.append(strategy_id)

        sql = f"""
            SELECT
                COUNT(*) AS total_trades,
                AVG(mae) AS avg_mae,
                MIN(mae) AS worst_mae,
                AVG(mfe) AS avg_mfe,
                MAX(mfe) AS best_mfe,
                AVG(CASE WHEN pnl > 0 THEN mae END) AS avg_mae_winners,
                AVG(CASE WHEN pnl < 0 THEN mae END) AS avg_mae_losers,
                AVG(CASE WHEN pnl > 0 THEN mfe END) AS avg_mfe_winners,
                AVG(CASE WHEN pnl < 0 THEN mfe END) AS avg_mfe_losers
            FROM trade_results
            WHERE {" AND ".join(where)}
        """
        row = self.conn.execute(sql, params).fetchone()
        return _row_to_dict(row) if row else {}

    def fetch_confidence_performance(
        self,
        symbol: str | None = None,
        strategy_id: str | None = None,
    ) -> list[dict]:
        where = ["pnl IS NOT NULL", "confidence IS NOT NULL"]
        params: list[Any] = []
        if symbol:
            where.append("symbol = ?")
            params.append(symbol)
        if strategy_id:
            where.append("strategy_id = ?")
            params.append(strategy_id)
        sql = f"""
            SELECT
                (confidence / 10) * 10 AS confidence_bucket,
                COUNT(*) AS total_trades,
                SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) AS wins,
                SUM(pnl) AS net_pnl,
                AVG(pnl) AS avg_pnl,
                AVG(pnl_pct) AS avg_pnl_pct
            FROM trade_results
            WHERE {" AND ".join(where)}
            GROUP BY (confidence / 10) * 10
            ORDER BY confidence_bucket ASC
        """
        rows = self.conn.execute(sql, params).fetchall()
        out = []
        for row in rows:
            item = _row_to_dict(row)
            total = item.get("total_trades") or 0
            wins = item.get("wins") or 0
            item["win_rate"] = round((wins / total) * 100, 2) if total else 0.0
            out.append(item)
        return out

    def fetch_signal_decision_summary(
        self,
        symbol: str | None = None,
        timeframe: str | None = None,
    ) -> dict:
        where = []
        params: list[Any] = []
        if symbol:
            where.append("symbol = ?")
            params.append(symbol)
        if timeframe:
            where.append("timeframe = ?")
            params.append(timeframe)
        where_sql = " WHERE " + " AND ".join(where) if where else ""
        rows = self.conn.execute(
            f"""
            SELECT reason, accepted, COUNT(*) AS count
            FROM signal_decisions
            {where_sql}
            GROUP BY reason, accepted
            ORDER BY count DESC
            """,
            params,
        ).fetchall()
        total = 0
        accepted = 0
        by_reason = []
        for row in rows:
            item = _row_to_dict(row)
            count = item.get("count") or 0
            total += count
            if item.get("accepted"):
                accepted += count
            by_reason.append(item)
        return {
            "total_decisions": total,
            "accepted_decisions": accepted,
            "rejected_decisions": total - accepted,
            "acceptance_rate": round((accepted / total) * 100, 2) if total else 0.0,
            "by_reason": by_reason,
        }

    def fetch_signal_decisions(
        self,
        symbol: str | None = None,
        timeframe: str | None = None,
        limit: int | None = None,
    ) -> list[dict]:
        where = []
        params: list[Any] = []
        if symbol:
            where.append("symbol = ?")
            params.append(symbol)
        if timeframe:
            where.append("timeframe = ?")
            params.append(timeframe)

        sql = "SELECT * FROM signal_decisions"
        if where:
            sql += " WHERE " + " AND ".join(where)
        if limit is not None:
            sql += " ORDER BY timestamp DESC, id DESC LIMIT ?"
            params.append(max(1, int(limit)))
            rows = self.conn.execute(sql, params).fetchall()
            return [_row_to_dict(row) for row in reversed(rows)]
        sql += " ORDER BY timestamp ASC, id ASC"
        return [_row_to_dict(row) for row in self.conn.execute(sql, params).fetchall()]

    def fetch_strategy_version_performance(
        self,
        symbol: str | None = None,
        strategy_id: str | None = None,
    ) -> list[dict]:
        where = ["pnl IS NOT NULL"]
        params: list[Any] = []
        if symbol:
            where.append("symbol = ?")
            params.append(symbol)
        if strategy_id:
            where.append("strategy_id = ?")
            params.append(strategy_id)
        rows = self.conn.execute(
            f"""
            SELECT
                strategy_version,
                COUNT(*) AS total_trades,
                SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) AS wins,
                SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) AS losses,
                SUM(pnl) AS net_pnl,
                AVG(pnl) AS avg_pnl,
                AVG(pnl_pct) AS avg_pnl_pct,
                MIN(pnl_pct) AS worst_trade_pct,
                MAX(pnl_pct) AS best_trade_pct
            FROM trade_results
            WHERE {" AND ".join(where)}
            GROUP BY strategy_version
            ORDER BY net_pnl DESC
            """,
            params,
        ).fetchall()
        out = []
        for row in rows:
            item = _row_to_dict(row)
            total = item.get("total_trades") or 0
            wins = item.get("wins") or 0
            item["win_rate"] = round((wins / total) * 100, 2) if total else 0.0
            out.append(item)
        return out

    def fetch_strategy_version_regime_performance(
        self,
        symbol: str | None = None,
        timeframe: str | None = None,
        strategy_id: str | None = None,
    ) -> list[dict]:
        where = ["tr.pnl IS NOT NULL"]
        params: list[Any] = []
        if symbol:
            where.append("tr.symbol = ?")
            params.append(symbol)
        if strategy_id:
            where.append("tr.strategy_id = ?")
            params.append(strategy_id)

        timeframe_filter = ""
        subquery_params: list[Any] = []
        if timeframe:
            timeframe_filter = " AND ec.timeframe = ?"
            subquery_params.append(timeframe)

        rows = self.conn.execute(
            f"""
            SELECT
                strategy_version,
                COALESCE(regime, 'unknown') AS regime,
                COUNT(*) AS total_trades,
                SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) AS wins,
                SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) AS losses,
                SUM(pnl) AS net_pnl,
                AVG(pnl) AS avg_pnl,
                AVG(pnl_pct) AS avg_pnl_pct
            FROM (
                SELECT
                    tr.*,
                    (
                        SELECT ec.regime
                        FROM entry_contexts ec
                        WHERE ec.symbol = tr.symbol
                          AND ec.strategy_id = tr.strategy_id
                          AND ec.strategy_version = tr.strategy_version
                          AND ec.timestamp <= tr.timestamp
                          {timeframe_filter}
                        ORDER BY ec.timestamp DESC, ec.id DESC
                        LIMIT 1
                    ) AS regime
                FROM trade_results tr
                WHERE {" AND ".join(where)}
            )
            GROUP BY strategy_version, COALESCE(regime, 'unknown')
            ORDER BY strategy_version ASC, net_pnl DESC
            """,
            subquery_params + params,
        ).fetchall()
        out = []
        for row in rows:
            item = _row_to_dict(row)
            total = item.get("total_trades") or 0
            wins = item.get("wins") or 0
            item["win_rate"] = round((wins / total) * 100, 2) if total else 0.0
            out.append(item)
        return out

    def fetch_shadow_trades(
        self,
        symbol: str | None = None,
        timeframe: str | None = None,
        limit: int | None = None,
    ) -> list[dict]:
        where = []
        params: list[Any] = []
        if symbol:
            where.append("symbol = ?")
            params.append(symbol)
        if timeframe:
            where.append("timeframe = ?")
            params.append(timeframe)
        sql = "SELECT * FROM shadow_trades"
        if where:
            sql += " WHERE " + " AND ".join(where)
        if limit is not None:
            sql += " ORDER BY entry_timestamp DESC, id DESC LIMIT ?"
            params.append(max(1, int(limit)))
            rows = self.conn.execute(sql, params).fetchall()
            return [_row_to_dict(row) for row in reversed(rows)]
        sql += " ORDER BY entry_timestamp ASC, id ASC"
        return [_row_to_dict(row) for row in self.conn.execute(sql, params).fetchall()]

    def fetch_open_shadow_trades(
        self,
        symbol: str | None = None,
        timeframe: str | None = None,
    ) -> list[dict]:
        where = ["status = 'open'"]
        params: list[Any] = []
        if symbol:
            where.append("symbol = ?")
            params.append(symbol)
        if timeframe:
            where.append("timeframe = ?")
            params.append(timeframe)
        return [
            _row_to_dict(row)
            for row in self.conn.execute(
                f"""
                SELECT * FROM shadow_trades
                WHERE {" AND ".join(where)}
                ORDER BY entry_timestamp ASC, id ASC
                """,
                params,
            ).fetchall()
        ]

    def fetch_shadow_summary(
        self,
        symbol: str | None = None,
        timeframe: str | None = None,
    ) -> dict:
        where = []
        params: list[Any] = []
        if symbol:
            where.append("symbol = ?")
            params.append(symbol)
        if timeframe:
            where.append("timeframe = ?")
            params.append(timeframe)
        where_sql = " WHERE " + " AND ".join(where) if where else ""
        row = self.conn.execute(
            f"""
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN status = 'open' THEN 1 ELSE 0 END) AS open,
                SUM(CASE WHEN status = 'closed' THEN 1 ELSE 0 END) AS closed,
                SUM(CASE WHEN pnl_pct > 0 THEN 1 ELSE 0 END) AS wins,
                SUM(CASE WHEN pnl_pct < 0 THEN 1 ELSE 0 END) AS losses,
                SUM(pnl_pct) AS net_pnl_pct,
                AVG(pnl_pct) AS avg_pnl_pct
            FROM shadow_trades
            {where_sql}
            """,
            params,
        ).fetchone()
        data = _row_to_dict(row) if row else {}
        closed = data.get("closed") or 0
        wins = data.get("wins") or 0
        data["win_rate"] = round((wins / closed) * 100, 2) if closed else 0.0
        return data

    def fetch_health(self) -> dict:
        run = self.conn.execute(
            "SELECT * FROM bot_runs ORDER BY started_at DESC LIMIT 1"
        ).fetchone()
        errors = self.conn.execute(
            "SELECT COUNT(*) AS count FROM bot_errors"
        ).fetchone()
        latest_equity = self.conn.execute(
            "SELECT * FROM equity_curve ORDER BY timestamp DESC, id DESC LIMIT 1"
        ).fetchone()
        open_position = self.conn.execute(
            "SELECT * FROM open_position_state LIMIT 1"
        ).fetchone()
        return {
            "latest_run": _row_to_dict(run) if run else None,
            "error_count": int(errors["count"] if errors else 0),
            "latest_equity": _row_to_dict(latest_equity) if latest_equity else None,
            "open_position": _row_to_dict(open_position) if open_position else None,
        }


def _iso(value: datetime) -> str:
    return value.isoformat()


def _json(value: Any) -> str:
    return json.dumps(value, default=_json_default, ensure_ascii=False, sort_keys=True)


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "value"):
        return value.value
    if hasattr(value, "item"):
        return value.item()
    if is_dataclass(value):
        return asdict(value)
    return str(value)


def _row_to_dict(row: sqlite3.Row) -> dict:
    data = dict(row)
    for key in ("indicators_json", "context_json", "details_json", "metadata_json"):
        if key in data:
            data[key.removesuffix("_json")] = _loads_json(data.pop(key))
    return data


def _loads_json(value: str | None) -> Any:
    if not value:
        return {}
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return {}
