# Arquitetura

## Fluxo por tick (a cada candle)

```
bot.py (TradingBot.run)
  └─ _tick()
       ├─ 1. fetch_ohlcv(150 candles)          ← ExchangeConnector
       ├─ 2. compute_indicators(df, cfg)        ← Indicators
       ├─ 3. trailing_stop.update(price)        ← TrailingStop   [se em posição]
       ├─ 4. _daily_loss_breached()             ← métricas internas
       ├─ 5. mtf.get_bias()                     ← MultiTimeframeAnalyzer [se fora de posição]
       ├─ 6. get_signal(ind, ...)               ← Strategy
       ├─ 7. filtro MTF (bloqueia compra se bearish)
       └─ 8. _execute_buy / _execute_sell       ← ExchangeConnector
```

## Diagrama de módulos

```
src/
  bot.py             ← TradingBot: loop principal, orquestra tudo
  config.py          ← Config (dataclass lida do .env)
  exchange.py        ← ExchangeConnector: ccxt + paper trading interno
  indicators.py      ← compute_indicators() → IndicatorData
  strategy.py        ← get_signal() → Signal enum
  simulation.py      ← Motor compartilhado (usado por backtest + optimizer)
  optimizer.py       ← GeneticOptimizer: evolui parâmetros
  mtf.py             ← MultiTimeframeAnalyzer: viés no TF superior
  trailing_stop.py   ← TrailingStop: stop que sobe com o preço
  position_sizing.py ← PositionSizer: % do saldo por confiança
  notifier.py        ← Telegram
  reconnect.py       ← ReconnectionManager: backoff exponencial
  scheduler.py       ← WeeklyScheduler: autotune automático
  metrics.py         ← append_metric() para logs JSONL
  report.py          ← Relatório semanal
  logger.py          ← setup_logger()
```

## Princípios de design

- **Motor único de simulação** — `simulation.py` é usado tanto pelo backtest quanto pelo optimizer. Nenhum drift entre eles.
- **Config como fonte única de verdade** — todos os parâmetros vêm do `.env` via `Config`. Nenhum magic number espalhado.
- **Sem estado global** — todo estado de posição fica no `TradingBot`. O `ExchangeConnector` tem o estado do paper trading interno.
- **Async end-to-end** — o loop principal é async/await; operações de exchange têm retry automático via `ReconnectionManager`.
