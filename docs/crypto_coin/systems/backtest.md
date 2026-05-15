# Sistema: Backtest

**Arquivos:** `backtest.py` (CLI), `src/simulation.py` (motor)

## Motor compartilhado

`simulation.py` é a fonte única da lógica de simulação. Tanto o backtest manual quanto o optimizer usam as mesmas funções:

| Função | Descrição |
|--------|-----------|
| `paper_process_candle(window, cfg, state, ...)` | Processa um candle e retorna trades gerados |
| `paper_finalize_open_position(state, last_price)` | Fecha posição aberta no fim do período |
| `PaperState` | Dataclass com estado da simulação: `balance`, `asset`, `buy_price`, `in_position` |

## Uso via CLI

```bash
# Últimos 90 dias
python backtest.py

# Período customizado
python backtest.py --days 180

# Par e exchange específicos
python backtest.py --symbol ETH/USDT --exchange bybit
```

## Saída

```
📊 Backtest — BTC/USDT (15m) — 90 dias
   Candles: 8640
   Trades:  47
   Win rate: 59%
   Retorno: +12.4%
   Buy & Hold: +8.1%
   Max drawdown: -6.2%
   Sharpe: 1.34
```

## Limitação conhecida

O backtest fecha a posição aberta no último candle pelo preço de fechamento. Em produção real, a posição seria carregada para o próximo período — o resultado do último trade pode ser levemente otimista.
