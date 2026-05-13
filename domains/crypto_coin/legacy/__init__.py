# Compatibility shim — src/ está sendo deprecado.
# Os módulos reais estão em: config/, core/, indicators/, strategies/, analytics/, etc.
# Imports antigos continuam funcionando durante a transição.

from config.settings import Config, load_config
from infra.logger import setup_logger
from infra.notifier import Notifier
from core.execution.exchange_connector import ExchangeConnector
from core.risk.trailing_stop import TrailingStop
from core.risk.position_sizing import PositionSizer
from core.engine.reconnect import ReconnectionManager
from core.engine.trading_engine import TradingBot
from indicators.technical import compute_indicators, Indicators, MarketRegime
from indicators.mtf import MultiTimeframeAnalyzer, MTFBias
from strategies.trend_following.strategy import Signal, get_signal, signal_description
from backtesting.simulation import (PaperState, paper_process_candle,
                                    paper_finalize_open_position, DEFAULT_INITIAL_BALANCE)
from analytics.metrics.calc import compute_all as compute_metrics
from autotune.optimizer import GeneticOptimizer, Individual, evaluate
from autotune.scheduler import WeeklyScheduler
