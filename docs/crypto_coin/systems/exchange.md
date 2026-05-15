# Sistema: Exchange Connector

**Arquivo:** `src/exchange.py` — classe `ExchangeConnector`

## Responsabilidades

- Abstrai a biblioteca ccxt para os outros módulos
- Fornece paper trading interno (sem precisar de API key)
- Normaliza respostas: sempre retorna `quote` (USDT) e `base` (ativo)

## Paper trading

Quando `PAPER_TRADING=true`, nenhuma ordem real é enviada. O connector mantém:

```python
_paper_balance: float   # Saldo em USDT
_paper_asset: float     # Quantidade do ativo comprado
_paper_buy_price: float # Preço de entrada da posição atual
```

**Slippage simulado:** 0.05% por side (`_SLIPPAGE = 0.0005`).  
Compra usa `preço × 1.0005`, venda usa `preço × 0.9995`.

## Métodos públicos

| Método | Descrição |
|--------|-----------|
| `connect()` | Inicializa conexão com a exchange (no-op em paper) |
| `fetch_ohlcv(limit)` | Retorna DataFrame OHLCV com índice de timestamp |
| `get_ticker_price()` | Retorna preço atual do par |
| `buy(quote_amount)` | Compra usando até `quote_amount` em USDT |
| `sell(asset_amount)` | Vende `asset_amount` do ativo |
| `get_balances()` | Retorna `{quote, base, quote_ccy, base_ccy}` |
| `close()` | Fecha conexão ccxt |

## Taxa simulada

`0.1%` por operação (mesmo valor da Binance spot padrão).

## Exchanges suportadas

`binance`, `bybit`, `kucoin`

KuCoin requer `API_PASSPHRASE` além de key e secret.
