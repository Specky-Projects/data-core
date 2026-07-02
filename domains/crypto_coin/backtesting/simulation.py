"""
Motor compartilhado de simulação (paper) — backtest e otimizador genético.

Mantém a mesma sequência de sinais/fees que o backtest oficial, para evitar drift
entre `backtest.py` e `src/optimizer.evaluate`.

Modo realista (realistic=True):
  - Intracandle SL/TP: verifica high/low do candle antes de avaliar o fechamento.
    Evita que a simulação "ignore" um stop que foi atingido intracandle.
  - Bar+1 execution: BUY é agendado no fechamento e executado no open do próximo
    candle — elimina lookahead bias (na vida real você não compra no close que
    gerou o sinal, mas no candle seguinte).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from domains.crypto_coin.indicators.technical import compute_indicators
from domains.crypto_coin.strategies.trend_following.strategy import Signal, get_signal

DEFAULT_INITIAL_BALANCE = 10_000.0
FEE_ROUND = 0.999  # ~0.1% por lado


@dataclass
class PaperState:
    balance: float
    asset: float = 0.0
    buy_price: float = 0.0
    in_position: bool = False
    pending_buy: bool = False   # bar+1: compra agendada para o próximo open


def paper_equity(state: PaperState, mark_price: float) -> float:
    if not state.in_position:
        return state.balance
    return state.balance + state.asset * mark_price


def paper_strategy_return_pct(equity: float, initial_balance: float) -> float:
    return (equity - initial_balance) / initial_balance * 100


def _make_sell_record(exec_price: float, buy_price: float, asset: float,
                      signal: Signal, bar_time: Any) -> tuple[dict, float]:
    gross = asset * exec_price
    net   = gross * FEE_ROUND
    pnl   = net - (asset * buy_price)
    rec: dict[str, Any] = {
        "side":    signal.value,
        "price":   exec_price,
        "pnl":     pnl,
        "pnl_pct": ((exec_price - buy_price) / buy_price) * 100,
    }
    if bar_time is not None:
        rec["time"] = bar_time
    return rec, net


def paper_process_candle(
    window: pd.DataFrame,
    cfg: Any,
    state: PaperState,
    *,
    initial_balance: float,
    bar_time: Any = None,
    min_buy_balance: float = 0.0,
    realistic: bool = False,
) -> tuple[PaperState, list[dict[str, Any]]]:
    """
    Um passo por candle: indicadores → get_signal → aplica BUY/SELL simulados.

    realistic=True ativa:
      - Execução bar+1: BUY sinalizado no fechamento executa no open do próximo candle.
      - Intracandle SL/TP: usa high/low do candle para verificar stop e take-profit
        antes de avaliar o sinal do fechamento.
    """
    out: list[dict[str, Any]] = []
    last_bar = window.iloc[-1]

    # ── Bar+1: executa compra pendente no open deste candle ────────────────
    if realistic and state.pending_buy and not state.in_position:
        open_px = float(last_bar.get("open", last_bar["close"]))
        spend   = state.balance * (cfg.trade_size_pct / 100)
        qty     = (spend * FEE_ROUND) / open_px
        state.balance  -= spend
        state.asset     = qty
        state.buy_price = open_px
        state.in_position  = True
        state.pending_buy  = False
        rec: dict[str, Any] = {"side": "BUY", "price": open_px}
        if bar_time is not None:
            rec["time"] = bar_time
        out.append(rec)

    # ── Intracandle SL/TP usando high/low ──────────────────────────────────
    if realistic and state.in_position:
        stop_px = state.buy_price * (1 - cfg.stop_loss_pct / 100)
        tp_px   = state.buy_price * (1 + cfg.take_profit_pct / 100)
        low_px  = float(last_bar.get("low",  last_bar["close"]))
        high_px = float(last_bar.get("high", last_bar["close"]))

        # Stop tem prioridade (cenário mais conservador quando ambos são atingidos)
        if low_px <= stop_px:
            rec, net = _make_sell_record(stop_px, state.buy_price, state.asset,
                                         Signal.STOP_LOSS, bar_time)
            out.append(rec)
            state.balance    += net
            state.asset       = 0.0
            state.buy_price   = 0.0
            state.in_position = False
            return state, out

        if high_px >= tp_px:
            rec, net = _make_sell_record(tp_px, state.buy_price, state.asset,
                                         Signal.TAKE_PROFIT, bar_time)
            out.append(rec)
            state.balance    += net
            state.asset       = 0.0
            state.buy_price   = 0.0
            state.in_position = False
            return state, out

    # ── Avalia sinal no fechamento ─────────────────────────────────────────
    ind = compute_indicators(window, cfg)
    if ind is None:
        return state, out

    eq     = paper_equity(state, ind.close)
    sr_pct = paper_strategy_return_pct(eq, initial_balance)
    buy_px = state.buy_price if state.in_position else None
    signal = get_signal(ind, state.in_position, buy_px, cfg, sr_pct)

    # ── Compra ────────────────────────────────────────────────────────────
    if signal in (Signal.BUY, Signal.RANGE_BUY) and not state.in_position and not state.pending_buy:
        if state.balance > min_buy_balance:
            if realistic:
                # Agenda para executar no open do próximo candle
                state.pending_buy = True
            else:
                spend = state.balance * (cfg.trade_size_pct / 100)
                qty   = (spend * FEE_ROUND) / ind.close
                state.balance    -= spend
                state.asset       = qty
                state.buy_price   = ind.close
                state.in_position = True
                rec = {"side": "BUY", "price": ind.close}
                if bar_time is not None:
                    rec["time"] = bar_time
                out.append(rec)

    # ── Venda (sinal de fechamento) ───────────────────────────────────────
    elif signal in (Signal.SELL, Signal.STOP_LOSS, Signal.TAKE_PROFIT, Signal.RANGE_SELL):
        if state.in_position:
            rec, net = _make_sell_record(ind.close, state.buy_price, state.asset,
                                         signal, bar_time)
            out.append(rec)
            state.balance    += net
            state.asset       = 0.0
            state.buy_price   = 0.0
            state.in_position = False

    return state, out


def paper_finalize_open_position(
    state: PaperState, last_price: float
) -> tuple[PaperState, list[dict[str, Any]]]:
    """Fecha posição aberta no último preço (fim da série histórica)."""
    records: list[dict[str, Any]] = []
    if not state.in_position or state.asset <= 0:
        return state, records
    net = state.asset * last_price * FEE_ROUND
    pnl = net - (state.asset * state.buy_price)
    state.balance += net
    records.append({"side": "SELL (fechamento)", "price": last_price, "pnl": pnl,
                     "pnl_pct": ((last_price - state.buy_price) / state.buy_price) * 100})
    state.asset       = 0.0
    state.buy_price   = 0.0
    state.in_position = False
    return state, records
