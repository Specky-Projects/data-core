# Sistema: Otimizador Genético

**Arquivo:** `src/optimizer.py` — classe `GeneticOptimizer`

## O que faz

Usa algoritmo genético para encontrar os melhores parâmetros da estratégia nos últimos N dias de dados históricos.

## Fluxo

```
1. Gera 40 indivíduos (conjuntos de parâmetros) aleatórios
2. Avalia cada um com backtest rápido (mesmo motor de simulation.py)
3. Seleciona os melhores (elitismo: top 20%)
4. Cruza os sobreviventes (crossover uniforme)
5. Aplica mutações (±1–3 steps por parâmetro, 25% chance)
6. Repete por 25 gerações
7. Retorna o melhor conjunto encontrado
```

## Espaço de busca

| Parâmetro | Min | Max | Step |
|-----------|-----|-----|------|
| `ma_fast` | 3 | 15 | 1 |
| `ma_slow` | 15 | 50 | 1 |
| `rsi_period` | 7 | 21 | 1 |
| `rsi_oversold` | 25 | 45 | 1 |
| `rsi_overbought` | 55 | 75 | 1 |
| `bb_period` | 10 | 30 | 1 |
| `bb_std` | 1.5 | 3.0 | 0.1 |
| `stop_loss_pct` | 1.0 | 8.0 | 0.5 |
| `take_profit_pct` | 2.0 | 15.0 | 0.5 |
| `trade_size_pct` | 10 | 40 | 5 |

## Função de fitness

```python
fitness = total_return * win_bonus * (1 + sharpe * 0.5) - trade_penalty

win_bonus    = win_rate / 50          # 1.0 = neutro (50% win rate)
sharpe_bonus = max(0, sharpe)
trade_penalty = max(0, (10 - trades) * 2)  # penaliza < 10 trades
```

Indivíduos com menos de 3 trades recebem `fitness = -999` (descartados).

## Validação walk-forward

O `WeeklyScheduler` divide os dados:
- **60 dias** para treino (otimização)
- **14 dias** para validação (out-of-sample)

Só atualiza o `.env` se a validação passar com retorno ≥ `min_val_return`.

## Saída

Atualiza automaticamente os valores no `.env` e recarrega o `Config` do bot sem reiniciar.
