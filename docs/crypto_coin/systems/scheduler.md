# Sistema: Scheduler (Auto-tuner automático)

**Arquivo:** `src/scheduler.py` — classe `WeeklyScheduler`

## O que faz

Executa o auto-tuner genético periodicamente sem interromper o trading. O resultado (melhores parâmetros) é aplicado ao `.env` e recarregado no bot ao vivo.

## Configuração

```env
AUTOTUNE_HOUR=3             # Hora do dia para rodar (padrão: 3h da manhã)
AUTOTUNE_INTERVAL_DAYS=7    # Intervalo entre otimizações (padrão: 7 dias)
```

## Comportamento na primeira subida

Na primeira vez que o bot sobe, o scheduler **não roda imediatamente**. Aguarda `AUTOTUNE_INTERVAL_DAYS` dias para evitar spike de CPU/API ao iniciar.

## Dados de treino/validação

| Período | Dias | Uso |
|---------|------|-----|
| Treino | 60 | Otimização genética |
| Validação | 14 | Out-of-sample (evita overfitting) |

Os melhores parâmetros só são aplicados se o retorno na validação ≥ `min_val_return` (padrão: 0%).

## Estado persistido

`logs/schedule_state.json` — salva `last_run` e `first_seen` para sobreviver a reinicializações do bot.

## Execução manual

```bash
python autotune.py
```

Ou como módulo standalone:

```bash
python -m src.scheduler
```
