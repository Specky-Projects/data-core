# Operational Recovery Flow — Phase R

> Document: `ai/docs/operational_recovery_flow.md`
> Phase: R — Autonomous Runtime Governance & Production Hardening
> Module: R-7 OperationalRecoveryEngine
> Updated: 2026-05-17

---

## Visao Geral

O `OperationalRecoveryEngine` (R-7) executa recovery controlado com um pipeline
obrigatorio de pre-checks, um catalogo de 8 acoes de recovery executadas em ordem
de prioridade, e post-checks de integridade. O sistema nunca executa recovery cego:
pre-checks reprovados resultam em todas as acoes marcadas como `SKIPPED`.

**Principio de prevencao de loop:** maximo 3 tentativas de recovery por hora no
mesmo contexto. Na 4a tentativa, a acao e marcada como `BLOCKED` e um incidente
`EMERGENCY` e criado automaticamente.

---

## 1. Tipos de Trigger de Recovery

| Trigger | Origem | Prioridade | Descricao |
|---|---|---|---|
| `MANUAL` | CLI / operador | Alta | Acionado explicitamente pelo operador via CLI |
| `WATCHDOG` | R-3 AutonomousServiceWatchdog | Alta | Servico travado, deadlock ou heartbeat perdido |
| `INCIDENT` | R-6 AutonomousIncidentManager | Alta | Incidente CRITICAL ou EMERGENCY ativo |
| `GUARDIAN` | Q-3 AutonomousLiveGuardian (Phase Q) | Media | Guardian emitiu ROLLBACK |
| `STARTUP_FAILURE` | R-1 AutonomousStartupManager | Alta | Boot falhou em subsistema critico |

### Prioridade de avaliacao quando multiplos triggers simultaneos

```
STARTUP_FAILURE > WATCHDOG > INCIDENT (EMERGENCY) > INCIDENT (CRITICAL) > GUARDIAN > MANUAL
```

O trigger de maior prioridade vira o `primary_trigger` do recovery record.
Todos os triggers ativos sao registrados em `triggers_evaluated`.

---

## 2. Pre-Checks Obrigatorios (5 checks)

Todos os 5 pre-checks devem passar. **Se qualquer BLOCKING falhar, todas as acoes de
recovery sao marcadas como `SKIPPED`** e um incidente CRITICAL e criado informando
que o recovery nao pode ser executado em condicoes seguras.

| # | Check | Tipo | O que verifica | Falha resulta em |
|---|---|---|---|---|
| 1 | `system_not_in_emergency_shutdown` | BLOCKING | `autonomous_runtime_state != SHUTDOWN` | Todas acoes SKIPPED |
| 2 | `no_active_conflicting_recovery` | BLOCKING | Nao ha outro recovery em andamento | Todas acoes SKIPPED |
| 3 | `attempt_count_within_limit` | BLOCKING | `attempts_last_hour < 3` | Todas acoes SKIPPED + incidente EMERGENCY |
| 4 | `data_directory_accessible` | BLOCKING | `DATA_DIR` existe e e gravavel | Todas acoes SKIPPED |
| 5 | `incident_manager_reachable` | WARNING | R-6 responde a chamadas | Warning no log, recovery continua |

### Schema do resultado de pre-check

```json
{
  "check_id": "attempt_count_within_limit",
  "check_type": "BLOCKING",
  "passed": true,
  "value": 1,
  "threshold": 3,
  "message": "1 attempt(s) in last hour (limit: 3)"
}
```

---

## 3. Catalogo de 8 Acoes de Recovery

As acoes sao executadas em ordem de prioridade (1 = maior prioridade).
Cada acao e independente: falha em uma nao bloqueia as demais, exceto onde indicado.

| # | Acao | Prioridade | Aplicavel a Triggers | Descricao |
|---|---|---|---|---|
| 1 | `restart_stalled_services` | 1 | WATCHDOG | Reinicia servicos com heartbeat perdido ou loop travado |
| 2 | `restore_operational_state` | 2 | STARTUP_FAILURE, WATCHDOG | Invoca R-2 para restaurar estado operacional completo |
| 3 | `reset_incident_counters` | 3 | INCIDENT, GUARDIAN | Zera contadores de incidentes INFO/WARNING resolvidos |
| 4 | `revalidate_environment` | 4 | STARTUP_FAILURE | Re-executa os 13 checks de ambiente do R-1 |
| 5 | `clear_stale_locks` | 5 | WATCHDOG, INCIDENT | Remove lock files e semaforos orfaos |
| 6 | `flush_and_reopen_logs` | 6 | Todos | Fecha e reabre todos os file handles de JSONL |
| 7 | `reset_stability_baseline` | 7 | INCIDENT (DEGRADED+) | Reinicia baseline do R-4 para nova sessao |
| 8 | `notify_governance_cycle` | 8 | Todos | Aciona ciclo de governanca R-8 imediato pos-recovery |

### Detalhes por acao

**Acao 1 — restart_stalled_services**
```
Entrada: lista de servicos com watchdog_triggered=True
Processo: para servico → aguarda 2s → reinicia
Sucesso: servico reporta heartbeat dentro de 30s
Falha: servico nao responde → escalado como CRITICAL no R-6
Dependencias: nenhuma
```

**Acao 2 — restore_operational_state**
```
Entrada: R-2 OperationalStateRestorationEngine
Processo: save_current_partial_state() → restore_state()
Sucesso: state_integrity_score >= 70
Falha: state_integrity_score < 70 → penalidade no integrity_score
Dependencias: DATA_DIR acessivel (pre-check 4)
```

**Acao 3 — reset_incident_counters**
```
Entrada: R-6 lista de incidentes INFO/WARNING AUTO_RESOLVED
Processo: limpa active_incidents.json para entradas resolvidas
Sucesso: operational_risk_score reduzido >= 10 pts
Falha: arquivo de incidentes inacessivel → skip
Dependencias: R-6 reachable (pre-check 5)
```

**Acao 4 — revalidate_environment**
```
Entrada: R-1 validate_environment()
Processo: re-executa os 13 checks de ambiente
Sucesso: env_validation_score >= 70
Falha: env_validation_score < 70 → recovery parcial com aviso
Dependencias: nenhuma
```

**Acao 5 — clear_stale_locks**
```
Entrada: DATA_DIR/*.lock files
Processo: verifica age > 5min → remove se orfao
Sucesso: zero lock files orfaos apos limpeza
Falha: lock file em uso por processo ativo → mantido
Dependencias: DATA_DIR acessivel (pre-check 4)
```

**Acao 6 — flush_and_reopen_logs**
```
Entrada: todos os file handles JSONL abertos
Processo: flush() → close() → reopen(mode='a')
Sucesso: todos os handles respondem sem IOError
Falha: handle especifico corrompido → rotacionado para novo arquivo
Dependencias: nenhuma
```

**Acao 7 — reset_stability_baseline**
```
Entrada: R-4 LongRunningStabilityEngine
Processo: salva snapshot atual → reinicia counters de decay/drift
Sucesso: stability_engine confirma reset
Falha: R-4 indisponivel → skip com warning
Dependencias: R-4 inicializado
```

**Acao 8 — notify_governance_cycle**
```
Entrada: R-8 AutonomousRuntimeGovernance
Processo: sinaliza ciclo imediato (sem aguardar proximo cron)
Sucesso: R-8 executa ciclo e retorna novo runtime_governance_score
Falha: R-8 nao responde → governance ciclo atrasado
Dependencias: R-8 inicializado
```

---

## 4. Post-Checks de Integridade

Apos execucao das acoes, 4 post-checks verificam se o sistema retornou a um
estado saudavel.

| # | Check | Threshold | Impacto no integrity_score |
|---|---|---|---|
| 1 | `watchdog_health_score` | >= 65 | +25 se passa |
| 2 | `operational_risk_score` | < 50 | +25 se passa |
| 3 | `state_integrity_score` | >= 70 | +25 se passa |
| 4 | `stability_score` | >= 55 | +25 se passa |

```
integrity_score = sum(25 pts × check_passed)
                = 0 a 100

Interpretacao:
  integrity_score >= 80 → recovery_success = True  (3 ou 4 checks passaram)
  integrity_score 60-79 → recovery_partial          (exatamente 2 checks passaram — DEGRADED)
  integrity_score < 60  → recovery_failed           (0 ou 1 check passou — novo incidente CRITICAL)
```

---

## 5. Fluxo Completo de Execucao de Recovery

```mermaid
flowchart TD
    T([Trigger recebido]) --> CHK_RATE{attempts_last_hour < 3?}

    CHK_RATE -->|NAO| BLOCKED[Marcar como BLOCKED\nCriar incidente EMERGENCY\nPersistir recovery_log.jsonl]
    BLOCKED --> END_BLOCKED([FIM — recovery bloqueado])

    CHK_RATE -->|SIM| PRE[Executar 5 Pre-Checks]
    PRE --> PC_PASS{Todos BLOCKING\npassaram?}

    PC_PASS -->|NAO| SKIP[Marcar todas as acoes\ncomo SKIPPED\nCriar incidente CRITICAL\n"recovery unsafe"]
    SKIP --> END_SKIP([FIM — recovery nao executado])

    PC_PASS -->|SIM| INC_ATT[Incrementar\nattempts_last_hour]
    INC_ATT --> EXEC[Executar 8 Acoes em ordem]

    EXEC --> A1[Acao 1: restart_stalled_services]
    A1 --> A2[Acao 2: restore_operational_state]
    A2 --> A3[Acao 3: reset_incident_counters]
    A3 --> A4[Acao 4: revalidate_environment]
    A4 --> A5[Acao 5: clear_stale_locks]
    A5 --> A6[Acao 6: flush_and_reopen_logs]
    A6 --> A7[Acao 7: reset_stability_baseline]
    A7 --> A8[Acao 8: notify_governance_cycle]

    A8 --> POST[Executar 4 Post-Checks]
    POST --> SCORE{integrity_score?}

    SCORE -->|>= 80| SUCCESS[recovery_success = True\nResolver incidente origem\nPersistir recovery_log.jsonl]
    SCORE -->|60-79| PARTIAL[recovery_partial = True\nIncidente DEGRADED criado\nPersistir recovery_log.jsonl]
    SCORE -->|< 60| FAIL[recovery_failed = True\nIncidente CRITICAL criado\nPersistir recovery_log.jsonl]

    SUCCESS --> END_OK([FIM — sistema saudavel])
    PARTIAL --> END_PARTIAL([FIM — monitoramento\nintensivo ativado])
    FAIL --> END_FAIL([FIM — aguarda\nintervencao manual])

    style SUCCESS fill:#1a5c2e,color:#fff
    style PARTIAL fill:#5c4a1a,color:#fff
    style FAIL fill:#5c1a1a,color:#fff
    style BLOCKED fill:#5c1a1a,color:#fff
    style SKIP fill:#5c1a1a,color:#fff
```

---

## 6. Recovery Scoring

### recovery_success_rate (historico)

```
recovery_success_rate = (successful_recoveries / total_attempts) × 100

onde:
  successful_recoveries = recoveries com integrity_score >= 80
  total_attempts = todas as tentativas (exceto BLOCKED e SKIPPED)

Thresholds:
  >= 70 → aceitavel
  50-69 → preocupante (alerta WARNING)
  < 50  → critico (alerta CRITICAL)
```

### integrity_score (por execucao)

Ver secao 4 — formula baseada em 4 post-checks com 25 pts cada.

### actions_completed_pct (por execucao)

```
actions_completed_pct = (acoes com status SUCCESS / acoes aplicaveis) × 100

Thresholds para classificacao:
  >= 80% → recovery considerado "completo"
  60-79% → recovery "parcial aceitavel"
  < 60%  → recovery "parcial insuficiente" → integrity_score penalizado
```

---

## 7. Quando Pular Recovery (Pre-Checks Reprovam)

```
Pre-check 1 FALHA (system in SHUTDOWN):
  → Todas as acoes: SKIPPED
  → Motivo: sistema em processo de encerramento, recovery seria destrutivo
  → Acao do operador: aguardar shutdown completo, reiniciar manualmente

Pre-check 2 FALHA (conflicting recovery):
  → Todas as acoes: SKIPPED
  → Motivo: dois recoveries simultaneos causariam corrupcao de estado
  → Acao do operador: aguardar recovery em andamento terminar

Pre-check 3 FALHA (attempts >= 3/hora):
  → Todas as acoes: BLOCKED (diferente de SKIPPED)
  → Incidente EMERGENCY criado automaticamente
  → Motivo: prevencao de restart infinito
  → Acao do operador: investigar causa raiz, resolver manualmente

Pre-check 4 FALHA (DATA_DIR inacessivel):
  → Todas as acoes: SKIPPED
  → Motivo: sem acesso ao DATA_DIR, acoes 2/3/5/6 falhariam de forma destrutiva
  → Acao do operador: corrigir permissoes de filesystem

Pre-check 5 FALHA (incident_manager inacessivel):
  → Recovery CONTINUA (WARNING apenas)
  → Acoes 3 e 8 podem falhar graciosamente
  → Motivo: nao e blocking — recovery pode ser util mesmo sem R-6
```

---

## 8. Transicoes de Estado do Recovery

```
[IDLE] ──────────── trigger recebido ──────────────→ [EVALUATING_PRECHECKS]

[EVALUATING_PRECHECKS]
    │── pre-checks PASS ──→ [IN_PROGRESS]
    │── BLOCKING FAIL ────→ [SKIPPED] ──→ [IDLE]
    └── attempts >= 3 ────→ [BLOCKED] ──→ [IDLE]

[IN_PROGRESS]
    │── actions executando ──→ [POST_CHECKING]

[POST_CHECKING]
    │── integrity >= 80 ──→ [COMPLETED_SUCCESS] ──→ [IDLE]
    │── integrity 60-79 ──→ [COMPLETED_PARTIAL] ──→ [IDLE]
    └── integrity < 60  ──→ [COMPLETED_FAILED]  ──→ [IDLE]

Nota: estados [COMPLETED_*] sao transitorios (< 1s).
      O sistema retorna a [IDLE] imediatamente apos persistir o resultado.
```

---

## 9. Recovery Parcial: o que acontece quando algumas acoes falham

```
Cenario: 5 de 8 acoes concluidas com sucesso

actions_completed_pct = 5/8 = 62.5%

[Acoes com falha sao registradas individualmente:]
  - action_id: restart_stalled_services, status: FAILED,
    error: "service live_controller did not recover within 30s"
  - action_id: restore_operational_state, status: FAILED,
    error: "state_integrity_score=55 below threshold 70"

[Post-checks executam normalmente]
  - watchdog_health_score: 58 → FAIL (abaixo de 65)
  - operational_risk_score: 45 → PASS (abaixo de 50)
  - state_integrity_score: 55 → FAIL (abaixo de 70)
  - stability_score: 60 → PASS (acima de 55)

integrity_score = 2 × 25 = 50 → recovery_failed

[Consequencia:]
  - recovery_partial_failure registrado no recovery_log.jsonl
  - Incidente CRITICAL criado: "Recovery failed: integrity_score=50"
  - Sistema em estado DEGRADED
  - Proximo recovery tentado somente se operador investigar e acionar manualmente
```

---

## 10. Integracao com Incident Manager (auto-create em falha)

```
recovery_success=True:
  → R-6.resolve_incident(incident_id=trigger_incident_id, reason="recovery_successful")
  → Nenhum novo incidente criado

recovery_partial=True (integrity 60-79):
  → R-6.create_incident(
        severity="DEGRADED",
        source="recovery_engine",
        description=f"Partial recovery: integrity_score={score}",
        correlation_id=recovery_id
    )
  → Incidente original permanece ativo (nao resolvido)

recovery_failed=True (integrity < 60):
  → R-6.create_incident(
        severity="CRITICAL",
        source="recovery_engine",
        description=f"Recovery failed: integrity_score={score}",
        correlation_id=recovery_id
    )
  → Incidente original escalado para severity+1 (se nao for EMERGENCY)

recovery_blocked=True (attempts >= 3):
  → R-6.create_incident(
        severity="EMERGENCY",
        source="recovery_engine",
        description="Recovery rate limit exceeded: 3 attempts in 1 hour",
        correlation_id=recovery_id
    )
```

---

## 11. Analise de Historico de Recoveries

```bash
# Ver todos os recoveries com resultado
cat data/recovery_log.jsonl | \
  python -c "
import sys, json
for l in sys.stdin:
    r = json.loads(l)
    print(f\"{r['evaluated_at'][:19]} | {r['trigger']:20} | {r.get('recovery_status','?'):25} | integrity={r.get('integrity_score','?')}\")
"

# Contar por status
cat data/recovery_log.jsonl | \
  python -c "
import sys, json
from collections import Counter
c = Counter()
for l in sys.stdin:
    r = json.loads(l)
    c[r.get('recovery_status', 'unknown')] += 1
for k, v in c.most_common():
    print(f'{k}: {v}')
"

# Ver recoveries da ultima hora
cat data/recovery_log.jsonl | \
  python -c "
import sys, json
from datetime import datetime, timezone, timedelta
cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
for l in sys.stdin:
    r = json.loads(l)
    ts = datetime.fromisoformat(r.get('evaluated_at', '2000-01-01T00:00:00+00:00'))
    if ts > cutoff:
        print(json.dumps(r, indent=2))
"
```

---

## 12. Prevencao de Restart Infinito (max 3 tentativas/hora)

### Mecanismo

```
Estado persistido em data/recovery_state.json:
{
  "attempts_last_hour": [
    "2026-05-17T14:10:00+00:00",
    "2026-05-17T14:25:00+00:00",
    "2026-05-17T14:38:00+00:00"
  ]
}

Antes de cada recovery:
  1. Filtrar timestamps com age > 60min (sliding window)
  2. Se len(filtrado) >= 3 → BLOCKED
  3. Se nao → adicionar timestamp atual e continuar
```

### Por que o limite e 3 e nao 1 ou 10?

- 1 seria muito restritivo: um recovery legitimo pode falhar por condicao transitoria
- 3 permite: primeira tentativa + retry imediato + segunda chance apos investigacao rapida
- 10 seria permissivo demais para um loop de crashes causando degradacao acumulada

### O que fazer quando BLOCKED

```
1. Investigar causa raiz nos logs:
   cat data/recovery_log.jsonl | tail -3 | python -m json.tool

2. Resolver manualmente o problema identificado

3. Aguardar sliding window de 1h expirar naturalmente
   OU resetar manualmente (somente em ambiente controlado):
   python -m domains.crypto_coin.research.operational_recovery_engine \
     --reset-attempt-counter --confirm

4. Verificar que R-6 incidente EMERGENCY foi resolvido antes de tentar novamente
```

---

## 13. CLIs Disponiveis

```bash
# Executar recovery (trigger manual)
python -m domains.crypto_coin.research.operational_recovery_engine --run

# Especificar trigger
python -m domains.crypto_coin.research.operational_recovery_engine --run --trigger manual
python -m domains.crypto_coin.research.operational_recovery_engine --run --trigger watchdog

# Status atual (tentativas, ultimo resultado, integrity)
python -m domains.crypto_coin.research.operational_recovery_engine --status

# Historico de recoveries
python -m domains.crypto_coin.research.operational_recovery_engine --history
python -m domains.crypto_coin.research.operational_recovery_engine --history --limit 10

# Output JSON
python -m domains.crypto_coin.research.operational_recovery_engine --json

# Apenas executar pre-checks (sem recovery)
python -m domains.crypto_coin.research.operational_recovery_engine --dry-run

# Reset de attempt counter (requer --confirm)
python -m domains.crypto_coin.research.operational_recovery_engine \
  --reset-attempt-counter --confirm
```
