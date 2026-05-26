# OOM prevention

## Sinais normais de burst

- `MEMORY_SPIKING` com retorno para patamar anterior.
- `memory_usage_ratio` abaixo de 75%.
- `cycle_duration` normal e `backlog_score` baixo.
- Sem incremento em `oom_kill_count`.

## Sinais de possivel leak

- `POSSIBLE_MEMORY_LEAK`.
- `growth_rate` positivo por muitos ciclos.
- Memoria nao retorna apos fim de ciclos pesados.
- Aumento simultaneo de `cycle_duration` e `backlog_score`.

## Quando aumentar memory limit

- Memoria acima de 75% por multiplos ciclos reais.
- Sem queda depois de finalizar coleta/normalizacao.
- Host ainda tem memoria disponivel e swap esta controlada.

## Quando escalar host

- Swap do host continua alta ou crescendo.
- Mais de um container entra em pressao.
- OOM recente se repete mesmo com limite do scheduler elevado.

## Interpretacao de OOM

OOM historico acumulado nao exige acao imediata. O gatilho operacional e OOM recente, restart loop, ou crescimento sustentado apos mitigacao.

