# Gestão de Risco

## Trailing Stop

Após comprar, o stop é dinâmico — sobe com o preço, nunca desce.

```
Compra: $100  →  Stop inicial: $97 (3% abaixo)
Preço sobe para $110  →  Stop sobe para $106.70 (3% abaixo de $110)
Preço cai para $106  →  Stop acionado: vende em $106 (lucro de +6%)
```

**Parâmetros:**
- `STOP_LOSS_PCT` — distância do trailing stop abaixo do pico
- `activate_pct=1.0` — só ativa depois de 1% de lucro (evita sair muito cedo)

## Take Profit fixo

Além do trailing stop, o bot vende automaticamente ao atingir `TAKE_PROFIT_PCT` de ganho.

## Position Sizing dinâmico

O tamanho da posição varia com o score de confiança do sinal:

| Confiança | % do saldo investido |
|-----------|---------------------|
| < 60 | `TRADE_SIZE_PCT × 0.6` |
| 60–74 | `TRADE_SIZE_PCT × 0.8` |
| 75–89 | `TRADE_SIZE_PCT × 1.0` |
| ≥ 90 | `TRADE_SIZE_PCT × 1.2` (máx 95%) |

## Limite de perda diária

Se `pnl_hoje / saldo_início_do_dia` cair abaixo de `-MAX_DAILY_LOSS_PCT`:
- O bot para de abrir novas ordens
- Aguarda a virada da meia-noite
- Reinicia os contadores

## Um trade por vez

`MAX_OPEN_TRADES=1` — o bot não abre nova posição enquanto já estiver comprado.

## Slippage simulado

No paper trading, compras usam `preço × 1.0005` e vendas usam `preço × 0.9995` (0.05% por lado) para resultados mais realistas.
