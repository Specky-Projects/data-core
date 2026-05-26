# Live Governance Architecture — Phase Q

> Document: `ai/docs/live_governance_architecture.md`
> Phase: Q — Micro-Live Execution & Capital-Protected Autonomy
> Updated: 2026-05-17

---

## Visao Geral

A Phase Q implementa uma camada de governanca live completa com 9 modulos independentes
orquestrados pelo `AutonomousLiveGovernance`. O principio central e **fail-safe first**:
qualquer duvida = paper.

---

## Principios de Design

### 1. Capital Safety First
Nenhum sinal, por mais confiante que seja, supera os limites hard de capital.
`LiveCapitalPreservationEngine` e o ultimo guardiao antes de qualquer ordem.

### 2. Independencia de Fases
Cada modulo Q opera de forma independente. Falha de um modulo nao bloqueia
o ciclo de governanca. O orchestrador reporta `phases_failed` mas continua.

### 3. Lineage Completo
Toda decisao autonoma gera um ID unico (UUID) e e persistida em JSONL append-only.
Nenhuma decisao e perdida.

### 4. Degradacao Gracosa
O sistema nunca para abruptamente. A sequencia e sempre:
`NORMAL → MONITORING → CONTRACTING → FROZEN → ROLLBACK`

### 5. Ativacao Explicita
Live requer `activate_live()` manual. Rollback e automatico. Reativacao requer
revisao das recovery_requirements.

---

## Modulos e Responsabilidades

### MicroLiveExecutionController (Q-1)
**Responsabilidade:** Portao de entrada para qualquer execucao live.

- Mantem state machine: `paper | live_micro | live_frozen | live_rollback`
- Valida pre-conditions por trade (governance_health, readiness, risk_score, exposure)
- Persiste estado em `data/live_execution_state.json` (nao JSONL — estado atual)
- Todo trade precisa de `validate_live_trade() → authorize_execution()`

**Limites hard:**
```
MAX_CAPITAL_LIVE_PCT   = 1.0%   # exposicao total
MAX_RISK_PER_TRADE_PCT = 0.25%  # por trade individual
MIN_GOVERNANCE_HEALTH  = 65
MIN_READINESS_SCORE    = 75
MAX_RISK_SCORE         = 50
```

### LiveExecutionAuditor (Q-2)
**Responsabilidade:** Auditoria continua de qualidade de execucao.

- Recebe `ExecutionRecord` (paper ou live) via `record_execution()`
- Calcula slippage_bps, fill_rate automaticamente no `ExecutionRecord.build()`
- `audit(window=50)` analisa ultimas 50 execucoes e detecta anomalias
- Score: `execution_quality_score` (0-100) com penalidades por slippage, fill, latencia

### AutonomousLiveGuardian (Q-3)
**Responsabilidade:** Protecao em tempo real durante execucao.

- Le audit_log e detecta 8 tipos de degradacao
- Computa `exchange_instability_score` baseado em tendencia de latencia e fill
- Acoes: soft contraction (60%) → hard contraction (35%) → freeze → rollback
- Nao executa as acoes — reporta decisoes para o orchestrador

### PaperVsLiveDivergenceEngine (Q-4)
**Responsabilidade:** Detectar divergencias sistematicas paper vs live.

- Separa registros por `mode` (paper | live) do mesmo audit_log
- Computa gaps: slippage_gap, fill_rate_gap, latency_gap_ms
- `divergence_score` alto indica que live e consistentemente pior que paper
- Detecta escalada de divergencia (segunda metade pior que primeira)

### LiveCapitalPreservationEngine (Q-5)
**Responsabilidade:** Enforcar limites hard de capital — inegociaveis.

- 5 checks formais com resultado binario (pass/fail)
- `approved_size_multiplier`: 1.0 → 0.50 → 0.25 → 0.0 conforme losses acumulam
- `daily_halt` e `weekly_halt` sao automaticos — nao ha override
- Requer `total_capital_usd` configurado corretamente

### LiveReadinessRevalidationEngine (Q-6)
**Responsabilidade:** Monitoramento continuo de prontidao durante operacao.

- Diferente do `MicroLiveReadinessEngine` (Phase P) que aprova entrada inicial
- Este monitora se condicoes *continuam* validas durante operacao
- Agrega 6 inputs de modulos distintos
- Status RED aciona rollback_recommended automaticamente

### AutonomousRollbackEngine (Q-7)
**Responsabilidade:** Decisao e execucao de rollback.

- Avalia 7 triggers em ordem de severidade
- Trigger mais severo vira o `primary_trigger` do incident
- Gera `RecoveryRequirements` especificas por severidade
- Persiste em `data/live_incident_reports.jsonl` para pos-mortem

### LiveExecutionReplayEngine (Q-8)
**Responsabilidade:** Validacao pos-hoc de cada execucao.

- Reproduz deterministicamente cada trade com contexto estimado
- `deviation_classification`: normal | elevated | anomalous | critical
- `execution_correctness`: slippage dentro do esperado para o regime detectado
- `replay_fidelity_score`: qualidade da reproducao

### AutonomousLiveGovernance (Q-9)
**Responsabilidade:** Orquestrar todos os modulos em ciclos periodicos.

- Executa 7 fases independentes (Q-2 ate Q-8) por ciclo
- Agrega scores com pesos definidos em constantes
- `autonomous_live_approval = True` apenas quando todos os gates passam
- Persiste ciclo completo em `data/live_governance_history.jsonl`

---

## Fluxo de Dados

```
Exchange (real ou testnet)
        │
        ▼
ExecutionRecord.build(mode="live", ...)
        │
        ▼
LiveExecutionAuditor.record_execution()
        │
        ├──→ data/live_execution_audit_log.jsonl
        │
        ▼
[Ciclo de Governanca — run_once()]
        │
        ├── Q-2: audit() → execution_quality_score
        │
        ├── Q-3: guardian.evaluate() → guardian_state, contraction_multiplier
        │
        ├── Q-4: divergence.evaluate() → divergence_score
        │
        ├── Q-5: capital.evaluate() → trading_allowed, approved_size_multiplier
        │
        ├── Q-6: revalidation.evaluate() → continuous_live_readiness_score
        │
        ├── Q-7: rollback.evaluate() → rollback_executed (se necessario)
        │
        └── Q-8: replay.replay_all() → replay_fidelity_score
                │
                ▼
        live_governance_score (formula ponderada)
        autonomous_live_approval (True/False)
```

---

## Separacao de Responsabilidades

| Modulo | Le de | Escreve em |
|---|---|---|
| Q-1 Controller | `live_execution_state.json` | `live_execution_state.json`, `live_execution_controller_log.jsonl` |
| Q-2 Auditor | — | `live_execution_audit_log.jsonl`, `live_execution_audit_summary.jsonl` |
| Q-3 Guardian | `live_execution_audit_log.jsonl` | `live_guardian_log.jsonl` |
| Q-4 Divergence | `live_execution_audit_log.jsonl` | `paper_vs_live_divergence_log.jsonl` |
| Q-5 Capital | `live_execution_audit_log.jsonl` | `live_capital_preservation_log.jsonl` |
| Q-6 Revalidation | 6 logs distintos (read-only) | `live_readiness_revalidation_log.jsonl` |
| Q-7 Rollback | 6 logs distintos (read-only) | `autonomous_rollback_log.jsonl`, `live_incident_reports.jsonl` |
| Q-8 Replay | `live_execution_audit_log.jsonl` | `live_execution_replay_log.jsonl` |
| Q-9 Governance | invoca Q2-Q8 | `live_governance_history.jsonl`, `live_governance_summary.jsonl` |

Regra: **nenhum modulo escreve no log de outro modulo**. Cada modulo tem seu proprio JSONL.

---

## Integracao com Phase P

Phase Q depende de Phase P para aprovacao inicial:

```
Phase P: MicroLiveReadinessEngine.evaluate()
  → approved_for_micro_live = True
  → live_readiness_score >= 75

         ↓ prerequisito

Phase Q: MicroLiveExecutionController.activate_live()
  → live_state: paper → live_micro
```

Se `approved_for_micro_live = False`, nao ativar live.

---

## Prometheus Integration

Todos os modulos Q importam `api.live_metrics` via `try/except`.
Sem API server: modulos funcionam normalmente, metricas nao sao emitidas.
Com API server: 14 metricas disponibilizadas automaticamente.

```python
# Padrao de importacao (todos os modulos Q)
try:
    from api.live_metrics import live_governance_score as _prom_score
    _METRICS_AVAILABLE = True
except ImportError:
    _METRICS_AVAILABLE = False
```
