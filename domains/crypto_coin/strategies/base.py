"""
Interface base para todas as estratégias.

Toda estratégia deve herdar de BaseStrategy e implementar generate_signal().
O engine chama strategy.generate_signal(context) — agnóstico de lógica interna.

Isso habilita:
  - Múltiplas estratégias simultâneas
  - Comparação de edge
  - A/B testing
  - Ensemble / portfolio allocation
  - Torneio de estratégias
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Any

import pandas as pd


@dataclass
class SignalContext:
    """
    Tudo que uma estratégia precisa para gerar um sinal.
    Agnóstico de indicadores — a estratégia decide o que usar.
    """
    symbol:     str
    timeframe:  str
    df:         pd.DataFrame     # OHLCV com pelo menos 150 candles
    cfg:        Any              # Config do sistema
    in_position: bool = False
    buy_price:   Optional[float] = None
    strategy_return_pct: float = 0.0
    metadata:    dict = field(default_factory=dict)


class BaseStrategy(ABC):
    """
    Interface que toda estratégia deve implementar.

    Exemplo de implementação mínima:
        class MyStrategy(BaseStrategy):
            @property
            def id(self) -> str: return "my_strategy_v1"

            def generate_signal(self, ctx: SignalContext) -> str:
                # sua lógica aqui
                return "HOLD"
    """

    @property
    @abstractmethod
    def id(self) -> str:
        """Identificador único da estratégia (slug, sem espaços)."""
        ...

    @property
    def name(self) -> str:
        """Nome legível. Padrão: usa o id."""
        return self.id

    @property
    def version(self) -> str:
        return "1.0"

    @abstractmethod
    def generate_signal(self, ctx: SignalContext) -> str:
        """
        Avalia o contexto e retorna um sinal.

        Returns:
            "BUY" | "SELL" | "HOLD" | "STOP_LOSS" | "TAKE_PROFIT"
            | "RANGE_BUY" | "RANGE_SELL" | "PAUSED"
        """
        ...

    def confidence(self, ctx: SignalContext) -> int:
        """Score de confiança para o sinal atual (0-100). Override opcional."""
        return 50

    def on_trade_closed(self, trade) -> None:
        """Callback chamado pelo engine após fechar um trade. Override opcional."""

    def __repr__(self) -> str:
        return f"<Strategy {self.id} v{self.version}>"
