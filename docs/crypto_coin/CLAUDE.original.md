# CryptoBot — Contexto para IA

Bot de trading automático de criptomoedas com análise técnica multi-indicador, trailing stop, multi-timeframe e auto-tuner genético.

## Arquitetura — monolito modular

```
bot.py              ← entry point: inicia o bot
backtest.py         ← entry point: roda backtest
autotune.py         ← entry point: otimização manual
deploy.py           ← entry point: deploy para VPS

core/
  schemas.py        ← Contratos de dados: MarketTick, Signal, Trade, Position, Execution, RegimeState
  events/bus.py     ← EventBus (pub/sub in-process)
  engine/
    trading_engine.py ← TradingBot (loop principal, event-driven)
    reconnect.py    ← ReconnectionManager (backoff exponencial)
  risk/
    trailing_stop.py  ← TrailingStop
    position_sizing.py← PositionSizer
  execution/
    exchange_connector.py ← ExchangeConnector (ccxt + paper trading)

strategies/
  base.py           ← BaseStrategy (ABC — strategy plugin interface)
  trend_following/
    strategy.py     ← Estratégia atual (MA + RSI + BB + regime)

indicators/
  technical.py      ← compute_indicators() → Indicators (ATR, VWAP, HV, breakout score)
  mtf.py            ← MultiTimeframeAnalyzer

analytics/
  metrics/calc.py   ← Sharpe, drawdown, expectancy, profit factor
  metrics/append.py ← append_metric() (JSON Lines)
  reports/weekly.py ← relatório semanal

backtesting/
  simulation.py     ← motor compartilhado (backtest + optimizer) — realista + bar+1

autotune/
  tuner.py          ← AutoTuner (orquestra otimização)
  optimizer.py      ← GeneticOptimizer
  scheduler.py      ← WeeklyScheduler

dashboard/
  server.py         ← Flask API (porta 8080)
  static/index.html ← UI (Tailwind + Chart.js)

infra/
  notifier.py       ← Telegram
  logger.py         ← setup_logger()

config/
  settings.py       ← Config (lê .env, valida)

src/                ← DEPRECADO — shim de compatibilidade temporário
tests/
docs/
```

## Regras de ouro

1. **Schemas são o contrato** — qualquer componente novo usa `core/schemas.py`; nenhum módulo depende do outro para entender dados
2. **`backtesting/simulation.py` é a fonte única** de lógica de simulação — backtest e optimizer rodam o mesmo código
3. **Config é a única fonte de parâmetros** — nenhum magic number; tudo vem do `.env` via `Config`
4. **Estratégia é um plugin** — herda `BaseStrategy`, implementa `generate_signal(ctx)` — o engine não sabe qual estratégia está usando
5. **Paper trading tem slippage** — `_SLIPPAGE = 0.0005` em `ExchangeConnector`; não remover
6. **Logs por par** — arquivo de trades é `logs/trades_{SYMBOL}.jsonl` (símbolo sanitizado, sem `/`)
7. **Scheduler não roda na subida** — espera `AUTOTUNE_INTERVAL_DAYS` antes da primeira otimização

## Configuração mínima

```env
EXCHANGE=binance
SYMBOL=BTC/USDT
TIMEFRAME=15m
PAPER_TRADING=true
PAPER_INITIAL_BALANCE=10000
```

Copie `.env.example` → `.env` e preencha.

## Rodar localmente

```bash
pip install -e .
python bot.py          # bot em loop
python backtest.py     # backtest
python autotune.py     # otimização
```

## Testes

```bash
pytest tests/
```

## Documentação completa

Ver `docs/` — context/ para visão geral, systems/ para detalhes de cada módulo.
