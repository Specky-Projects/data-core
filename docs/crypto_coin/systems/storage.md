# Storage Layer

Camada de persistencia do cerebro do bot.

## Backend

- Padrao local: `sqlite:///data/bot_storage.sqlite3`
- Producao planejada: PostgreSQL + TimescaleDB

O adapter atual implementa SQLite com `sqlite3` da biblioteca padrao. URLs
`postgresql://` ja sao reconhecidas, mas ainda retornam erro explicito ate o
adapter de producao existir.

## Tabelas

- `market_snapshots`: candle OHLCV e indicadores calculados no tick.
- `entry_contexts`: contexto completo no momento em que uma entrada e aceita.
- `trade_results`: execucao detalhada de compra/venda, slippage, P&L, MAE/MFE e fees.
- `regime_history`: historico de regime, confianca e medidas como ATR, HV e ADX.
- `equity_curve`: curva de equity por tick com saldo, posicao e P&L realizado.
- `open_position_state`: estado vivo da posicao aberta para retomada apos restart.
- `bot_runs`: cada execucao do bot com status e periodo.
- `signal_decisions`: sinais aceitos, bloqueados e ignorados com motivo.
- `shadow_trades`: entradas teoricas do modo shadow live, stop/take e resultado.
- `bot_errors`: erros estruturados para auditoria e healthcheck.

## Configuracao

```env
STORAGE_URL=sqlite:///data/bot_storage.sqlite3
STRATEGY_VERSION=v1.0
SHADOW_LIVE_ENABLED=false
MAX_TRADES_PER_DAY=0
COOLDOWN_AFTER_LOSS_MINUTES=0
MAX_CONSECUTIVE_LOSSES=0
```

O JSONL antigo de trades continua sendo gravado para compatibilidade; o SQLite
passa a ser a fonte estruturada para analise e memoria operacional.

## Leituras e analytics

O backend SQLite tambem expoe consultas para:

- trades recentes
- curva de equity
- performance por regime
- estatisticas de MAE/MFE
- performance por versao de estrategia
- resumo do shadow live

A camada `analytics.storage_analysis` agrega essas consultas em:

- `storage_overview(...)`: resumo operacional completo.
- `weak_regimes(...)`: regimes com amostra minima e P&L negativo.
- `stop_take_profit_hints(...)`: diagnostico baseado em MAE/MFE historico.

Cada entrada, trade e decisao passa a carregar `strategy_version`. Ao alterar
uma regra, incremente `STRATEGY_VERSION` para comparar P&L, win rate e pior/melhor
trade por versao no dashboard sem misturar historicos.

## Decisao operacional

A camada `analytics.decision_support` usa os dados persistidos para:

- bloquear entradas em regimes com amostra minima, P&L negativo e win rate fraco;
- exigir mais confianca quando o regime tem P&L negativo, mas ainda nao justifica bloqueio;
- gerar sugestoes diagnosticas de stop loss e take profit a partir de MAE/MFE.

As sugestoes de stop/take nao alteram parametros automaticamente. Elas aparecem no
dashboard como calibracao operacional para revisao humana.

O modo `ai_advisory` gera recomendacoes para a propria camada de IA em
`analytics.decision_support.advisory_report`; nada depende de revisao humana.
Quando os buckets de confianca mais baixos apresentam P&L negativo e buckets
superiores sustentam P&L positivo, a IA sugere testar um confidence gate em
paper/shadow por 7 dias antes de bloquear live.

Tambem sao expostos:

- performance por bucket de confianca;
- resumo de sinais aceitos/rejeitados por motivo;
- performance por versao da estrategia;
- performance cruzada por versao + regime;
- score de qualidade do setup (`weak`, `medium`, `strong`, `excellent`);
- decisoes autonomas da IA por estagio (`observe`, `shadow_test`, `paper_test`,
  `candidate_live`);
- healthcheck com ultima execucao, erros, equity mais recente e posicao aberta.
- relatorio textual em `analytics.storage_report.build_storage_report`.

O dashboard mostra aceitos vs rejeitados, motivos de bloqueio, recomendacoes do
modo IA, performance por bucket de confianca, versoes da estrategia, comparacao
versao/regime e resultado shadow live.

## Protecoes e shadow live

As protecoes contra overtrading sao opcionais e ficam desligadas por padrao com
valor `0`. Quando habilitadas, podem bloquear novas entradas por:

- limite maximo de trades fechados no dia;
- cooldown apos o ultimo loss;
- sequencia maxima de losses recentes.

O modo shadow live registra a entrada teorica quando um sinal de compra passa nos
filtros, sem enviar ordem extra. A cada candle ele fecha a simulacao se o low
tocar o stop teorico ou o high tocar o take teorico. Isso permite comparar a
decisao em tempo real contra paper/live sem alterar execucao.

`analytics.shadow_compare.shadow_paper_comparison` pareia trades shadow fechados
com trades paper/live proximos no tempo e calcula o delta medio entre resultado
teorico e executado.

Losses fechados recebem uma classificacao heuristica em `loss_type`, como
`valid_technical_stop`, `false_breakout`, `sideways_market`,
`stop_too_tight`, `late_entry` ou `slippage_fee_killed_trade`.

## Estado aberto

Quando uma compra e executada, o bot salva:

- preco de entrada
- quantidade
- confianca da entrada
- minima/maxima da posicao
- trailing stop atual
- maior preco visto pelo trailing
- status de ativacao do trailing

No restart, o `TradingBot` tenta restaurar esse estado antes do primeiro tick. Ao
fechar a posicao, o estado aberto e removido.

Depois de restaurar, o bot compara o estado salvo com o saldo base reportado pela
exchange/conector. Se houver divergencia, ele mantem o bot em modo "em posicao"
para evitar dupla compra e registra um erro estruturado.

## Replay

`backtesting.storage_replay` carrega `market_snapshots` em ordem cronologica para
replays e futuros backtests baseados nos dados reais observados pelo bot.

`filter_replay_summary` resume o comportamento atual dos filtros usando
`signal_decisions`. A avaliacao de outcome dos sinais bloqueados ainda depende de
um passo futuro: precificar cada decisao contra candles posteriores.

`replay_current_strategy` ja reprocessa os snapshots candle por candle com a
estrategia atual, simula entradas/saidas por stop/take e compara o sinal novo
com a decisao antiga gravada em `signal_decisions`. O dashboard mostra P&L
simulado, trades, drawdown, mudanca de sinal e mudanca de aceite.

O replay tambem precifica sinais bloqueados por filtros. Para cada decisao
`blocked_*`, ele olha os candles seguintes e estima se o stop, o take ou o preco
final do horizonte teria sido atingido. Esse resultado entra nas decisoes da IA
para manter ou relaxar filtros em shadow/paper.

Os endpoints do dashboard aceitam janela de replay por query string:
`/api/storage?start=2026-05-01&end=2026-05-13` ou
`/api/status?start=2026-05-01&end=2026-05-13`.
