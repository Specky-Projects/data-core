# Estratégia de Trading

## Regime de mercado

O ADX determina o regime antes de qualquer sinal:

| ADX | Regime | Estratégia ativa |
|-----|--------|-----------------|
| > 25 | `TRENDING_UP` / `TRENDING_DOWN` | Cruzamento de MAs |
| 20–25 | Transição | Ambas com critério mais rígido |
| < 20 | `RANGING` | Reversão nas bandas (RANGE_BUY/SELL) |

## Sinais

### Modo tendência (ADX > 25)

**BUY** — qualquer uma das condições:
- MA rápida cruza acima MA lenta (golden cross) + RSI sobrevendido
- Preço fecha abaixo banda inferior + RSI sobrevendido

**SELL** — qualquer uma das condições:
- MA rápida cruza abaixo MA lenta (dead cross) + RSI sobrecomprado
- Take profit atingido (`price ≥ buy_price × (1 + TP%)`)
- Stop loss atingido (`price ≤ buy_price × (1 - SL%)`)

### Modo lateral (ADX < 20)

**RANGE_BUY** — preço toca banda inferior + RSI sobrevendido (critério relaxado)

**RANGE_SELL** — preço toca banda superior OU RSI sobrecomprado

## Score de confiança (0–100)

Combina 4 fatores antes de entrar:

| Fator | Contribuição máxima |
|-------|---------------------|
| RSI (distância do limiar) | 30 pts |
| Volume (acima da média) | 25 pts |
| ADX (força da tendência) | 25 pts |
| Banda de Bollinger (posição) | 20 pts |

Mínimo para entrar: **55/100**.

## Filtros de proteção

- **Multi-timeframe** — bloqueia compra se TF superior está em viés BEARISH
- **Buy & Hold threshold** — pausa entradas se mercado subiu > 15% mais que a estratégia (evita perseguir o topo)
- **Daily loss limit** — para de operar se perda diária ≥ `MAX_DAILY_LOSS_PCT`

## Parâmetros configuráveis

Todos os limiaresestão no `.env` e são otimizados pelo auto-tuner:

```
MA_FAST, MA_SLOW, RSI_PERIOD
RSI_OVERSOLD, RSI_OVERBOUGHT
BB_PERIOD, BB_STD
STOP_LOSS_PCT, TAKE_PROFIT_PCT
TRADE_SIZE_PCT
```
