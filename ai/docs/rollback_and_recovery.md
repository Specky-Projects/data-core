# Rollback and Recovery — Phase Q

> Document: `ai/docs/rollback_and_recovery.md`
> Phase: Q — Micro-Live Execution & Capital-Protected Autonomy
> Updated: 2026-05-17

---

## Visao Geral

O sistema Phase Q implementa rollback totalmente autonomo com 7 triggers em ordem de
severidade. Todo rollback gera um incident report para pos-mortem e define
recovery_requirements especificas para retorno ao live.

---

## Triggers de Rollback

### Severity 1: Guardian Rollback (Mais Critico)
**Modulo:** `AutonomousLiveGuardian`
**Condicao:** Guardian emitiu `guardian_state=ROLLBACK`
```
Causa: losses_consecutivos >= 5 AND recent_hit_rate < 35%
Acao: transition_to_paper() imediato
Recovery: EXIGE revisao manual antes de reativar
```

### Severity 2: Readiness RED
**Modulo:** `LiveReadinessRevalidationEngine`
**Condicao:** `readiness_status = RED` (score < 40)
```
Causa: soma de penalidades > 60 pontos
Acao: rollback recomendado + incident gerado
Recovery: EXIGE revisao manual antes de reativar
```

### Severity 3: Capital Halt
**Modulo:** `LiveCapitalPreservationEngine`
**Condicao:** `trading_allowed = False`
```
Causas possiveis:
  - 4+ losses consecutivos → capital_freeze
  - daily_drawdown >= 2% → daily_halt
  - weekly_drawdown >= 4% → weekly_halt
Recovery: automatica apos reset de contadores (fim do dia/semana)
         OU zero losses por 3+ ciclos
```

### Severity 4: Exchange Degradation
**Modulo:** `LiveExecutionAuditor`
**Condicao:** `exchange_degradation = True`
```
Causa: slippage_deterioration + fill_inconsistency + latency_spike simultaneos
Acao: rollback para investigar exchange
Recovery: verificar conectividade, fees, limitacoes da exchange
```

### Severity 5: Divergence Critical
**Modulo:** `PaperVsLiveDivergenceEngine`
**Condicao:** `divergence_score > 70`
```
Causa: live consistentemente muito pior que paper
Acao: rollback para investigar microestrutura
Recovery: verificar timing de ordens, spread real, depth
```

### Severity 6: Governance Collapse
**Modulo:** Leitura de `governance_history.jsonl`
**Condicao:** `governance_health_score < 50`
```
Causa: sistema de governanca Phase O/P degradado
Acao: nao e seguro operar sem governanca funcional
Recovery: aguardar recovery da camada de governanca Phase O
```

### Severity 7: Manual Override (Menos Critico)
**Trigger:** CLI `--trigger manual`
**Condicao:** Operador acionou manualmente
```
Uso: manutencao planejada, atualizacao de parametros, investigacao
Recovery: manual, sem requirements obrigatorios
```

---

## Fluxo de Rollback Autonomo

```
Trigger detectado pelo AutonomousRollbackEngine
           │
           ▼
Identificar primary_trigger (menor severity number)
           │
           ▼
Gerar incident_id (UUID)
           │
           ▼
Coletar estado pre-rollback:
  - pre_rollback_governance
  - pre_rollback_exec_quality
  - pre_rollback_readiness
  - pre_rollback_guardian_state
  - pre_rollback_divergence
           │
           ▼
Definir RecoveryRequirements
  (manual_review_required = True se severity <= 2)
           │
           ▼
Persistir incident em data/live_incident_reports.jsonl
           │
           ▼
[AutonomousLiveGovernance detecta rollback_executed=True]
           │
           ▼
autonomous_live_approval = False
           │
           ▼
[Operador aciona transition_to_paper() ou guardian aciona automaticamente]
           │
           ▼
live_state: live_micro → live_rollback → paper
```

---

## Incident Report — Estrutura

```json
{
  "incident_id": "INCIDENT-abc123def456",
  "rollback_executed": true,
  "rollback_timestamp": "2026-05-17T14:32:11.123456+00:00",
  "rollback_reason": "guardian_state=ROLLBACK rollback_triggered=True",
  "trigger_type": "guardian_rollback",
  "trigger_severity": 1,

  "triggers_evaluated": [
    {"trigger_type": "guardian_rollback", "trigger_severity": 1, "triggered": true, "evidence": "..."},
    {"trigger_type": "readiness_red",     "trigger_severity": 2, "triggered": false, "evidence": "..."},
    ...
  ],
  "triggers_fired": 1,

  "pre_rollback_governance": 58.5,
  "pre_rollback_exec_quality": 45.2,
  "pre_rollback_readiness": 38.0,
  "pre_rollback_guardian_state": "ROLLBACK",
  "pre_rollback_divergence": 32.1,

  "recovery_requirements": {
    "governance_health_min": 70.0,
    "execution_quality_min": 70.0,
    "readiness_score_min": 80.0,
    "cycles_clean_required": 3,
    "governance_cycles_min": 2,
    "manual_review_required": true,
    "estimated_recovery_desc": "Revisao manual obrigatoria antes de reativar live."
  },

  "post_mortem_reference": "INCIDENT-abc123def456",
  "recommendation": "ROLLBACK EXECUTADO [severity=1 trigger=guardian_rollback]...",
  "evaluated_at": "2026-05-17T14:32:11.123456+00:00"
}
```

---

## Recovery Process

### Passo 1: Verificar Incident Report
```bash
# Ver ultimo incident
tail -1 data/live_incident_reports.jsonl | python -m json.tool

# Ver todos os incidents
cat data/live_incident_reports.jsonl | python -c \
  "import sys,json; [print(json.dumps(json.loads(l), indent=2)) for l in sys.stdin]"
```

### Passo 2: Avaliar Recovery Requirements

Para severity 1 e 2 (revisao manual obrigatoria):
- [ ] Investigar causa raiz do rollback
- [ ] Verificar se parametros precisam ser ajustados
- [ ] Confirmar que exchange esta funcional
- [ ] Validar dados de execucao historicos

Para severity 3-7 (recovery automatizavel):
```bash
# Verificar se conditions foram corrigidas
python -m domains.crypto_coin.research.live_readiness_revalidation_engine
python -m domains.crypto_coin.research.live_capital_preservation_engine
python -m domains.crypto_coin.research.autonomous_live_guardian
```

### Passo 3: Revalidar Prontidao

```bash
# Executar ciclo completo de validacao Phase P
python -m domains.crypto_coin.research.autonomous_validation_loop

# Verificar readiness score
python -m domains.crypto_coin.research.micro_live_readiness_engine

# Verificar governance health
python -m domains.crypto_coin.research.autonomous_governance --run
```

### Passo 4: Verificar Recovery Requirements

```
Cheklist pre-reativacao:
  [ ] governance_health >= 70 por 2+ ciclos consecutivos
  [ ] execution_quality >= 70 (ultimas 20 execucoes)
  [ ] readiness_score >= 80
  [ ] zero deteccoes criticas por 3+ ciclos de governanca
  [ ] revisao manual completada (se severity <= 2)
  [ ] rollback_events_total estavel (sem novos incidents)
```

### Passo 5: Reativar Live

```bash
# Somente apos todos os checks passarem
python -m domains.crypto_coin.research.micro_live_execution_controller --activate

# Confirmar estado
python -m domains.crypto_coin.research.micro_live_execution_controller --status

# Monitorar primeiro ciclo apos reativacao
python -m domains.crypto_coin.research.autonomous_live_governance --run
```

---

## Rollback Manual (Emergencia)

Para rollback imediato sem esperar o ciclo de governanca:

```bash
# Opcao 1: Freeze imediato (sem novas ordens, rollback nao executado)
python -m domains.crypto_coin.research.micro_live_execution_controller --freeze

# Opcao 2: Rollback gracioso completo
python -m domains.crypto_coin.research.micro_live_execution_controller --to-paper

# Opcao 3: Via rollback engine (gera incident report)
python -m domains.crypto_coin.research.autonomous_rollback_engine --trigger manual
```

---

## Historico de Rollbacks

```bash
# Ver todos os rollbacks com trigger
cat data/autonomous_rollback_log.jsonl | \
  python -c "import sys,json; [print(json.loads(l).get('trigger_type','?'), json.loads(l).get('evaluated_at','?')) for l in sys.stdin if json.loads(l).get('rollback_executed')]"

# Contar por trigger type
cat data/autonomous_rollback_log.jsonl | \
  python -c "
import sys, json
from collections import Counter
c = Counter()
for l in sys.stdin:
    r = json.loads(l)
    if r.get('rollback_executed'):
        c[r.get('trigger_type', 'unknown')] += 1
for k,v in c.most_common():
    print(f'{k}: {v}')
"
```

---

## Prevencao de Rollbacks Desnecessarios

O sistema tem degradacao gracosa para minimizar rollbacks precipitados:

```
1. Primeiro sinal de problema → MONITORING (sem acao)
2. Segundo sinal confirma → CONTRACTING (reducao de tamanho)
3. Terceiro sinal simultâneo → FROZEN (sem novas ordens)
4. Condicao critica confirmada → ROLLBACK
```

Rollback so ocorre quando:
- 5+ losses consecutivos AND hit_rate < 35% (guardian)
- Readiness score < 40 (acumulado de multiplos problemas)
- Ou trigger especifico critico (exchange_degradation, capital_halt, etc.)

Rollback NAO ocorre por um unico evento isolado.
