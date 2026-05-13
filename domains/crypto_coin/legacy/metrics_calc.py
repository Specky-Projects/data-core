"""
Métricas de performance para trades fechados.
Usado pelo dashboard e pelo autotune (fitness function).
"""

from __future__ import annotations
import math


def sharpe_ratio(pnl_pcts: list[float]) -> float | None:
    """
    Sharpe por trade (não anualizado).
    pnl_pcts: lista de retornos percentuais por trade (ex: [+2.1, -1.3, +4.0])
    """
    n = len(pnl_pcts)
    if n < 2:
        return None
    mean = sum(pnl_pcts) / n
    variance = sum((r - mean) ** 2 for r in pnl_pcts) / (n - 1)
    std = math.sqrt(variance)
    if std == 0:
        return None
    return round(mean / std, 3)


def max_drawdown(equity_values: list[float]) -> float:
    """
    Drawdown máximo em % — queda máxima de pico a vale na curva de equity.
    """
    if len(equity_values) < 2:
        return 0.0
    peak   = equity_values[0]
    max_dd = 0.0
    for v in equity_values:
        if v > peak:
            peak = v
        if peak > 0:
            dd = (peak - v) / peak * 100
            if dd > max_dd:
                max_dd = dd
    return round(max_dd, 2)


def expectancy(pnl_list: list[float]) -> float | None:
    """
    Expectancy: retorno médio por trade em valor absoluto.
    Responde: 'em média, quanto ganho (ou perco) por trade?'
    """
    if not pnl_list:
        return None
    return round(sum(pnl_list) / len(pnl_list), 2)


def profit_factor(pnl_list: list[float]) -> float | None:
    """
    Profit Factor = lucro bruto / perda bruta.
    > 1.5 é bom. < 1 = sistema perdedor.
    """
    gross_profit = sum(p for p in pnl_list if p > 0)
    gross_loss   = abs(sum(p for p in pnl_list if p < 0))
    if gross_loss == 0:
        return None if gross_profit == 0 else 999.0
    return round(gross_profit / gross_loss, 2)


def compute_all(trades: list[dict], initial_balance: float) -> dict:
    """
    Recebe lista de trades SELL com campos 'pnl' e 'pnl_pct'.
    Retorna dict com todas as métricas.
    """
    # Aceita qualquer trade com pnl (lado real="SELL", backtest="VENDER"/"STOP LOSS"/etc.)
    sells = [t for t in trades if t.get("pnl") is not None]
    if not sells:
        return {}

    pnl_list  = [t["pnl"] for t in sells]
    pnl_pcts  = [t.get("pnl_pct") or (t["pnl"] / initial_balance * 100) for t in sells]

    # Equity curve para drawdown
    equity = initial_balance
    eq_values = [initial_balance]
    for p in pnl_list:
        equity += p
        eq_values.append(equity)

    wins   = [p for p in pnl_list if p > 0]
    losses = [p for p in pnl_list if p < 0]

    return {
        "sharpe":        sharpe_ratio(pnl_pcts),
        "max_drawdown":  max_drawdown(eq_values),
        "expectancy":    expectancy(pnl_list),
        "profit_factor": profit_factor(pnl_list),
        "avg_win":       round(sum(wins)   / len(wins),   2) if wins   else 0.0,
        "avg_loss":      round(sum(losses) / len(losses), 2) if losses else 0.0,
        "total_trades":  len(sells),
    }
