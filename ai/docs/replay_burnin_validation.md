# Replay Burn-In Validation — Phase S S-5

## Objetivo

Garantir que os logs de operação acumulados ao longo de múltiplas sessões representam uma **linha do tempo contínua e íntegra**, sem corrupções, lacunas temporais ou quebras de sessão que possam mascarar problemas operacionais.

## Conceito de "Replay Session"

Cada arquivo JSONL de uma fonte de dados representa uma "sessão" de replay. Para que o burn-in seja válido, cada sessão deve ter:

1. **Registros parseáveis** — sem erros JSON
2. **Continuidade temporal** — sem gaps > 30 min entre registros consecutivos
3. **Completeness razoável** — pelo menos 50% dos registros esperados para o período

## Sessões Auditadas

```python
REPLAY_TARGETS = [
    ("live_readiness",       "data/live_readiness_revalidation_log.jsonl"),
    ("governance",           "data/runtime_governance_log.jsonl"),
    ("guardian",             "data/live_guardian_log.jsonl"),
    ("stability",            "data/stability_log.jsonl"),
    ("capital_preservation", "data/capital_preservation_log.jsonl"),
    ("execution_audit",      "data/live_execution_audit_summary.jsonl"),
    ("burnin",               "data/runtime_burnin_log.jsonl"),
    ("operational_drift",    "data/operational_drift_log.jsonl"),
]
```

## Algoritmo de Gap Detection

```python
timestamps = sorted([extract_ts(rec) for rec in records])

for i in range(1, len(timestamps)):
    gap_min = (timestamps[i] - timestamps[i-1]) / 60
    if gap_min > GAP_THRESHOLD_MINUTES:  # 30 min
        gap_count += 1
        max_gap = max(max_gap, gap_min)
```

**Por que 30 min?** Os módulos operacionais rodam em ciclos de ~5-15 min. Uma lacuna de 30 min indica que o daemon estava morto por pelo menos 2 ciclos — sinal de instabilidade real.

## Completeness Ratio

```python
expected_interval = 15.0  # minutos
expected_records  = max(1.0, span_minutes / expected_interval)
completeness      = min(1.0, len(records) / expected_records)
```

Se completeness < 50%, a sessão é classificada como `degraded`.

## Status de Sessão

```
healthy   → parse_errors < 10%, gaps ≤ 3, completeness ≥ 50%
degraded  → gaps > 3 OU completeness < 50%
corrupt   → parse_errors > 10% do total de linhas
missing   → arquivo não existe
```

## Score Formula

```python
# replay_burnin_score: weighted health
weights = {"healthy": 1.0, "degraded": 0.5, "corrupt": 0.1, "missing": 0.0}
replay_burnin = (Σ weights[c.status] / total) × 100

# replay_continuity_score: penalise gaps
gap_penalty = min(total_gaps × 5.0, 50.0)
replay_continuity = max(0, replay_burnin - gap_penalty)

# replay_consistency_score: penalise parse errors
parse_ratio = total_parse_errors / total_lines
replay_consistency = max(0, 100 × (1 - parse_ratio × 10))
```

## Interpretação de Resultados

| Cenário | Causa provável | Ação |
|---|---|---|
| Todas sessões `missing` | Sistema nunca rodou | Executar Phase Q/R |
| Muitas sessões `degraded` | Daemons de coleta instáveis | Verificar app/main.py scheduler |
| Sessões `corrupt` | Bug no processo de escrita | Inspecionar o módulo correspondente |
| Muitos gaps | Reinicializações frequentes | Verificar startup_log.jsonl |
| completeness < 50% | Ciclos muito espaçados | Ajustar intervalo do scheduler |

## Relação com S-1

O `replay_burnin_score` é um dos inputs do `burnin_readiness_score` (S-9):
```
burnin_readiness = S1×0.50 + S5×0.30 + S6×0.20
```

Um sistema pode ter boa estabilidade instantânea (S-1 alto) mas história de gaps (S-5 baixo), indicando que **a estabilidade não é sustentada** — o burn-in ainda não está validado.
