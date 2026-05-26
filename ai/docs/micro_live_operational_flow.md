# Micro-Live Operational Flow — Phase Q

> Document: `ai/docs/micro_live_operational_flow.md`
> Phase: Q — Micro-Live Execution & Capital-Protected Autonomy
> Updated: 2026-05-17

---

## Pre-Requisitos para Ativar Live

Antes de qualquer execucao live, os seguintes requisitos devem ser satisfeitos:

### 1. Gates Phase P (MicroLiveReadinessEngine)
```
governance_cycles      >= 3       [BLOCKING]
execution_decisions    >= 5       [BLOCKING]
no_runaway_behavior    = True     [BLOCKING]
governance_stable      = True     [BLOCKING]
autonomy_stability_score >= 60    [BLOCKING]
capital_survival_score >= 65      [BLOCKING]
```

### 2. Verificacao Manual
```bash
# Verificar aprovacao Phase P
python -m domains.crypto_coin.research.micro_live_readiness_engine

# Verificar estado do controller
python -m domains.crypto_coin.research.micro_live_execution_controller --status
```

### 3. Ativacao Explicita
```bash
# Ativar modo live_micro (requer live_state=paper)
python -m domains.crypto_coin.research.micro_live_execution_controller --activate
```

---

## Fluxo Por Trade (Ciclo de Vida de Uma Ordem)

```
[1] SINAL GERADO
    ↓
    strategy_signal(confidence=0.72, side="buy", symbol="BTC/USDT")

[2] VALIDACAO PRE-TRADE (Q-1)
    ↓
    MicroLiveExecutionController.validate_live_trade(
        confidence=0.72,
        risk_score=35.0,          # do AdaptiveRiskIntelligence
        portfolio_exposure=0.008, # exposicao atual / capital total
        governance_health=75.0,   # do AutonomousGovernance
        readiness_score=80.0,     # do MicroLiveReadinessEngine
    )
    → TradeValidationResult.allowed = True/False
    → approved_size_pct = 0.0025  # max 0.25% do capital

[3] AUTORIZACAO FINAL (Q-1)
    ↓
    MicroLiveExecutionController.authorize_execution(validation_result)
    → bool (True apenas se allowed=True E live_state=live_micro)

[4] SIZING (Q-1 + Q-5)
    ↓
    # Clipping por capital ceiling
    max_usd = enforce_micro_capital(requested_usd)
    # Ajuste por contraction multiplier (Q-3)
    actual_usd = max_usd * guardian.contraction_multiplier
    # Ajuste por capital preservation (Q-5)
    actual_usd = actual_usd * capital.approved_size_multiplier

[5] EXECUCAO NA EXCHANGE
    ↓
    order = exchange.create_order(symbol, side, size=actual_usd/price)
    fill  = exchange.get_fill(order.id)

[6] REGISTRO (Q-2)
    ↓
    record = ExecutionRecord.build(
        mode="live", symbol="BTC/USDT", side="buy",
        expected_price=65000.0,
        executed_price=fill.price,
        requested_size=actual_size,
        filled_size=fill.filled_size,
        latency_ms=fill.latency_ms,
        fee_usd=fill.fee,
    )
    LiveExecutionAuditor.record_execution(record)
    # Persiste em data/live_execution_audit_log.jsonl
```

---

## Fluxo de Ciclo de Governanca

Executado periodicamente (recomendado: a cada 5-15 minutos durante operacao live):

```bash
python -m domains.crypto_coin.research.autonomous_live_governance --run
```

### Sequencia interna do ciclo:

```
run_once()
│
├── [Q-2] LiveExecutionAuditor.audit(window=50)
│     → execution_quality_score
│     → detections: slippage_deterioration, fill_inconsistency, ...
│
├── [Q-3] AutonomousLiveGuardian.evaluate()
│     → guardian_state: NORMAL | MONITORING | CONTRACTING | FROZEN | ROLLBACK
│     → contraction_multiplier: 1.0 | 0.60 | 0.35 | 0.15
│     → rollback_triggered: bool
│
├── [Q-4] PaperVsLiveDivergenceEngine.evaluate()
│     → divergence_score: 0-100
│     → slippage_gap_bps, fill_rate_gap, latency_gap_ms
│
├── [Q-5] LiveCapitalPreservationEngine.evaluate()
│     → trading_allowed: bool
│     → approved_size_multiplier: 1.0 | 0.50 | 0.25 | 0.0
│     → capital_frozen, daily_halt, weekly_halt
│
├── [Q-6] LiveReadinessRevalidationEngine.evaluate()
│     → continuous_live_readiness_score: 0-100
│     → readiness_status: GREEN | YELLOW | ORANGE | RED
│     → rollback_recommended: bool
│
├── [Q-7] AutonomousRollbackEngine.evaluate()
│     → rollback_executed: bool
│     → trigger_type, trigger_severity
│     → recovery_requirements (se rollback)
│
├── [Q-8] LiveExecutionReplayEngine.replay_all()
│     → avg_fidelity_score
│     → pct_correct_execution, pct_anomalous
│
└── [Agregacao]
      live_governance_score = formula ponderada
      autonomous_live_approval = True/False
      → Persiste em data/live_governance_summary.jsonl
```

---

## Estados e Transicoes

### Estado Normal (GREEN)
```
guardian_state = NORMAL
readiness_status = GREEN
live_governance_score >= 75
trading_allowed = True
autonomous_live_approval = True
→ Operacao normal. Trades autorizados.
```

### Estado de Atencao (YELLOW/MONITORING)
```
guardian_state = MONITORING
readiness_status = YELLOW
live_governance_score 55-75
trading_allowed = True
→ Monitoramento intensivo. Trades ainda autorizados.
   Verificar proximos ciclos.
```

### Estado de Contracao (ORANGE/CONTRACTING)
```
guardian_state = CONTRACTING
readiness_status = ORANGE
live_governance_score 40-55
contraction_multiplier = 0.60 ou 0.35
trading_allowed = True (mas tamanho reduzido)
→ Ordens com tamanho reduzido automaticamente.
   Alerta para revisao humana.
```

### Estado de Freeze (FROZEN)
```
guardian_state = FROZEN
live_governance_score < 40
trading_allowed = False
autonomous_live_approval = False
→ Sem novas ordens. Aguardar recuperacao das metricas.
```

### Estado de Rollback (ROLLBACK executado)
```
rollback_executed = True
live_state = paper (apos transition_to_paper())
→ Incident report gerado.
   Revisao de recovery_requirements necessaria.
   Ativacao manual obrigatoria para retornar ao live.
```

---

## Verificacoes Recomendadas (Checklist Operacional)

### Antes de ativar live:
```bash
# 1. Aprovacao Phase P
python -m domains.crypto_coin.research.autonomous_validation_loop

# 2. Status do controller
python -m domains.crypto_coin.research.micro_live_execution_controller --status

# 3. Auditoria de execucoes paper recentes
python -m domains.crypto_coin.research.live_execution_auditor --json

# 4. Revalidacao de prontidao
python -m domains.crypto_coin.research.live_readiness_revalidation_engine
```

### Durante operacao (monitoramento):
```bash
# Ciclo completo de governanca
python -m domains.crypto_coin.research.autonomous_live_governance --run

# Guardian isolado
python -m domains.crypto_coin.research.autonomous_live_guardian

# Capital preservation
python -m domains.crypto_coin.research.live_capital_preservation_engine

# Divergencia paper vs live
python -m domains.crypto_coin.research.paper_vs_live_divergence_engine
```

### Apos sessao live:
```bash
# Replay de todas execucoes
python -m domains.crypto_coin.research.live_execution_replay_engine

# Auditoria completa
python -m domains.crypto_coin.research.live_execution_auditor --json

# Verificar incidents
cat data/live_incident_reports.jsonl | python -m json.tool
```

---

## Capital Allocation Durante Live

Com capital_ceiling_usd = $200 (default):

```
Max exposicao total live:    $200 × 1.0%  =  $2.00
Max por trade individual:    $200 × 0.25% =  $0.50

Pos 2 losses consecutivos:   × 0.50  → max $1.00 total, $0.25/trade
Pos 3 losses consecutivos:   × 0.25  → max $0.50 total, $0.125/trade
Pos 4 losses consecutivos:   FREEZE  → $0 (sem novas ordens)
```

**Este e o capital real em risco. Configurar `total_capital_usd` corretamente antes de ativar live.**

---

## Logs para Monitoramento

```bash
# Ultimos ciclos de governanca
tail -5 data/live_governance_summary.jsonl | python -c "import sys,json; [print(json.dumps(json.loads(l), indent=2)) for l in sys.stdin]"

# Incidents de rollback
cat data/live_incident_reports.jsonl

# Guardian log
tail -10 data/live_guardian_log.jsonl

# Audit summary
tail -5 data/live_execution_audit_summary.jsonl
```
