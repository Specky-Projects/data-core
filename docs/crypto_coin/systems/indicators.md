# Sistema: Indicadores

**Arquivo:** `src/indicators.py` — função `compute_indicators(df, cfg) → IndicatorData`

## IndicatorData (dataclass de saída)

```python
close: float
ma_fast: float | None
ma_slow: float | None
rsi: float | None
bb_upper: float | None
bb_lower: float | None
adx: float | None
volume_ratio: float | None    # volume atual / média dos últimos 20
regime: MarketRegime
buy_and_hold_pct: float       # retorno acumulado do ativo desde 1º candle
confidence: int               # 0–100
```

## Indicadores calculados

| Indicador | Biblioteca | Descrição |
|-----------|-----------|-----------|
| SMA (MA fast/slow) | pandas | Médias simples de fechamento |
| RSI | numpy | Força relativa (Wilder) |
| Bollinger Bands | pandas | Média ± N desvios padrão |
| ADX | numpy | Força da tendência (Average Directional Index) |
| Volume ratio | pandas | Volume atual ÷ média de 20 períodos |

## Market Regime

```python
class MarketRegime(Enum):
    TRENDING_UP   = "TRENDING_UP"
    TRENDING_DOWN = "TRENDING_DOWN"
    RANGING       = "RANGING"
    UNKNOWN       = "UNKNOWN"
```

Determinado pelo ADX:
- `ADX > 25` + `MA fast > MA slow` → `TRENDING_UP`
- `ADX > 25` + `MA fast < MA slow` → `TRENDING_DOWN`
- `ADX < 20` → `RANGING`

## Score de confiança

Calculado somando pontos de 4 dimensões (máx 100):

- **RSI** (30 pts) — quão longe está do limiar de sobrevendido/sobrecomprado
- **Volume** (25 pts) — volume > 1.5× média = 25 pts; > 1.0× = 12 pts
- **ADX** (25 pts) — ADX > 30 = 25 pts; > 25 = 15 pts; > 20 = 8 pts
- **Bollinger** (20 pts) — preço tocando ou além da banda = 20 pts
