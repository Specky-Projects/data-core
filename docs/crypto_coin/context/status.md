# Status de Desenvolvimento

Última atualização: 2026-05-11

## Estado geral

O projeto está **funcional e em produção** (paper trading). Todos os módulos core estão implementados e testados.

## Módulos prontos

| Módulo | Status | Notas |
|--------|--------|-------|
| Loop principal (`bot.py`) | ✅ Pronto | v4 com todos os recursos |
| Exchange connector | ✅ Pronto | Binance, Bybit, KuCoin |
| Indicadores técnicos | ✅ Pronto | MA, RSI, BB, ADX, volume |
| Estratégia de sinais | ✅ Pronto | Tendência + lateral |
| Trailing stop | ✅ Pronto | Com ativação por lucro mínimo |
| Multi-timeframe | ✅ Pronto | Filtro de viés no TF superior |
| Position sizing | ✅ Pronto | Dinâmico por confiança |
| Backtest | ✅ Pronto | Motor compartilhado com optimizer |
| Otimizador genético | ✅ Pronto | 40 indivíduos, 25 gerações |
| Scheduler semanal | ✅ Pronto | Persistência em disco |
| Telegram notifier | ✅ Pronto | Opcional |
| Deploy script | ✅ Pronto | VPS Linux + systemd |
| Testes unitários | ⚠️ Parcial | 3 arquivos de teste (MTF, simulation, strategy) |

## Bugs corrigidos (2026-05-11)

- `_rand_param` no optimizer usava aritmética float imprecisa — substituído por `np.arange`
- `AUTOTUNE_HOUR` e `AUTOTUNE_INTERVAL_DAYS` eram hardcoded — agora vêm do `.env`
- Paper trading não simulava slippage — adicionado 0.05% por side
- Nome do arquivo de log `trades.jsonl` não incluía o par — agora é `trades_{SYMBOL}.jsonl`

## Próximos passos sugeridos

- [ ] Adicionar suporte a múltiplos pares simultaneamente
- [ ] Dashboard web com gráfico de equity curve
- [ ] Cobertura de testes > 80%
- [ ] Suporte a ordens limit (além de market)
- [ ] Integração com banco de dados para histórico de trades
