# Collector Reliability Flow — Phase S S-4

## O Problema dos Collectors Mortos

Em sistemas de monitoramento JSONL, um collector "morto" continua existindo como arquivo — ele só para de ser atualizado. O Grafana continua mostrando os últimos valores sem indicar que o dado é antigo. O S-4 resolve isso classificando **cada arquivo** por idade.

## Arquitetura de Coleta

```
Módulos Phase Q/R
  │  (escreve registros periodicamente)
  ▼
data/*.jsonl  ←── S-4 escaneia todos estes arquivos
  │
  ├── live_guardian_log.jsonl        (Guardian — ciclo ~5min)
  ├── watchdog_log.jsonl             (Watchdog — ciclo ~5min)
  ├── runtime_governance_log.jsonl   (Governance — ciclo ~10min)
  ├── stability_log.jsonl            (Stability — ciclo ~15min)
  ├── live_execution_audit_summary.jsonl
  ├── live_capital_preservation_log.jsonl
  ├── live_readiness_revalidation_log.jsonl
  └── ... (todos os *.jsonl)
```

## Algoritmo de Classificação

```python
def _classify_age(age_min):
    if age_min < 60:    return "fresh"    # < 1h
    if age_min < 360:   return "recent"   # 1-6h
    if age_min < 1440:  return "stale"    # 6-24h
    return "dead"                          # > 24h
```

## Parse Health Check

Para cada arquivo, o S-4 também verifica integridade do JSONL linha a linha:

```python
for line in lines:
    try:
        obj = json.loads(line)
        record_count += 1
    except json.JSONDecodeError:
        parse_errors += 1
```

Parse errors indicam processo de escrita com bug ou truncamento de arquivo.

## Core vs Non-Core Collectors

**Core collectors** são os 8 arquivos fundamentais para o funcionamento do sistema. Se algum destes está `missing`, é gerada uma issue crítica separada de `missing_core_count`.

**Non-core collectors** são arquivos extras encontrados em `data/` — incluídos na análise mas não penalizam o score de forma crítica.

## Score Formulas

```
# Reliability: % de arquivos atuais (fresh + recent)
collector_reliability_score = (fresh + recent) / total × 100

# Normalization: % de linhas sem erro de parse
normalization_integrity_score = (1 - parse_errors / total_lines) × 100

# Freshness: score ponderado por bucket
data_freshness_score = (fresh×1.0 + recent×0.7 + stale×0.3) / total × 100
```

## Interpretação Prática

| Score | Interpretação |
|---|---|
| reliability ≥ 85 | Pipeline de dados saudável |
| reliability 60-84 | Alguns collectors atrasados |
| reliability < 60 | Vários daemons podem estar mortos |
| normalization < 99 | Bugs de escrita ou arquivos corrompidos |
| data_freshness < 70 | Dados predominantemente stale/dead |

## Diagnóstico de Falha

```
collector_reliability_score baixo?
  │
  ├── missing_core_count > 0?
  │     → Módulos Phase Q/R nunca executaram
  │     → Rodar: python -m domains.crypto_coin.research.autonomous_startup_manager
  │
  ├── dead_count alto?
  │     → Daemons pararam faz >24h
  │     → Verificar: ps aux | grep python
  │     → Reiniciar: app/main.py
  │
  ├── stale_count alto?
  │     → Daemons atrasados (6-24h de atraso)
  │     → Verificar scheduler interval em app/main.py
  │
  └── total_parse_errors > 0?
        → Bug em processo de escrita
        → Identificar módulo pelo filename e inspecionar _persist()
```

## Relação com Outros Módulos

- **S-2** (Metrics Integrity) usa `mtime` como proxy — o S-4 é mais granular, verificando também parse health e record count
- **S-5** (Replay Burn-In) depende de bons collectors — arquivos dead/corrupt causam sessões `missing`/`corrupt` no S-5
- **S-8** (Drift Analyzer) usa os últimos 10 registros por arquivo — se o arquivo é dead, o S-8 retorna `no_data` para aquela dimensão

## Relação com observability_readiness_score

```
observability_readiness = S2×0.40 + S3×0.30 + S4×0.30
```

O S-4 tem peso 30% no cluster de observabilidade. Um pipeline de coleta morto impacta diretamente a maturidade operacional.
