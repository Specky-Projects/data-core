# Sistema: Bot (loop principal)

**Arquivo:** `src/bot.py` — classe `TradingBot`

## Responsabilidades

- Orquestra todos os outros módulos
- Mantém o estado de posição (`in_position`, `buy_price`, `position_size`)
- Controla métricas diárias e totais
- Dispara relatório semanal toda segunda-feira

## Estado interno

```python
in_position: bool          # Se há posição aberta
buy_price: float | None    # Preço de entrada
position_size: float       # Quantidade do ativo comprada
entry_confidence: int      # Score de confiança na entrada (0-100)
trailing_stop: TrailingStop | None

trades_today: int
pnl_today: float
total_trades: int
winning_trades: int
total_pnl: float
day_start_balance: float
```

## Ciclo do tick

1. `_check_day_reset()` — reseta contadores se virou o dia
2. `fetch_ohlcv(150)` — busca candles com retry
3. `compute_indicators()` — calcula todos os indicadores
4. `trailing_stop.update(price)` — verifica se stop foi atingido
5. `_daily_loss_breached()` — pausa se limite diário foi atingido
6. `mtf.get_bias()` — viés do TF superior (só se fora de posição)
7. `get_signal()` — gera o sinal da estratégia
8. Filtro MTF — bloqueia BUY se viés BEARISH
9. `_execute_buy` ou `_execute_sell`

## Arquivo de trades

Salvo em `logs/trades_{SYMBOL}.jsonl` (ex.: `trades_BTC_USDT.jsonl`).

Cada linha é um JSON:
```json
{
  "timestamp": "2025-05-11T03:00:00",
  "symbol": "BTC/USDT",
  "side": "BUY",
  "price": 62500.0,
  "amount": 0.00016,
  "pnl": null,
  "signal": null,
  "confidence": 78,
  "paper": true
}
```

## Configurações relevantes

`TIMEFRAME`, `SYMBOL`, `PAPER_TRADING`, `PAPER_INITIAL_BALANCE`, `MAX_DAILY_LOSS_PCT`, `AUTOTUNE_HOUR`, `AUTOTUNE_INTERVAL_DAYS`
