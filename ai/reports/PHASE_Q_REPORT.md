# Phase Q — Micro-Live Execution & Capital-Protected Autonomy
## Implementation Report

> Generated: 2026-05-17
> Status: **COMPLETE**
> Level upgrade: `L8` → live

---

## 1. Objetivo

Construir a camada de **execucao live controlada** com protecos de capital autonoma:

- Implementar portao formal de entrada para execucao live (paper → live_micro)
- Auditar qualidade de execucao em tempo real (slippage, fill, latencia)
- Proteger capital com limites hard inegociaveis
- Detectar degradacao de exchange e acionar contracao/rollback autonomo
- Comparar execucao paper vs live e detectar divergencias sistematicas
- Revalidar continuamente a prontidao live durante operacao
- Gerar incident reports detalhados para pos-analise de rollbacks

**O objetivo NAO e maximizar lucro — e sobrevivencia de capital e operabilidade controlada.**

---

## 2. Arquitetura Phase Q

```
AutonomousLiveGovernance (Q-9 — orchestrator live)
│
├── Q-1  MicroLiveExecutionController ── state machine paper/live_micro/frozen/rollback
│                                        validate_live_trade(), authorize_execution()
│                                        emergency_freeze(), transition_to_paper()
│
├── Q-2  LiveExecutionAuditor ─────────  ExecutionRecord.build() → record_execution()
│                                        audit(window=50) → ExecutionAuditReport
│                                        detects: slippage_deterioration, fill_inconsistency,
│                                                 latency_spike, exchange_degradation
│
├── Q-3  AutonomousLiveGuardian ───────  8 deteccoes: loss_sequence, hit_rate_degradation,
│                                        drawdown_acceleration, overtrading, confidence_collapse,
│                                        volatility_mismatch, exchange_instability, behavioral_anomaly
│                                        5 acoes: NORMAL→MONITORING→CONTRACTING→FROZEN→ROLLBACK
│
├── Q-4  PaperVsLiveDivergenceEngine ── scores: divergence_score, live_consistency, execution_alignment
│                                        detects: slippage_gap, fill_gap, latency_gap,
│                                                 divergence_escalation, execution_bias
│
├── Q-5  LiveCapitalPreservationEngine  Hard limits: 1% total, 0.25%/trade, 2% daily DD, 4% weekly DD
│                                        acoes: contracao_50%, contracao_25%, capital_freeze
│                                        2 losses → contracao | 4 losses → freeze
│
├── Q-6  LiveReadinessRevalidationEngine  continuous_live_readiness_score
│                                          GREEN>=75 | YELLOW>=55 | ORANGE>=40 | RED<40
│                                          RED → rollback automatico recomendado
│
├── Q-7  AutonomousRollbackEngine ─────  7 triggers (severity 1-7): guardian_rollback,
│                                        readiness_red, capital_halt, exchange_degradation,
│                                        divergence_critical, governance_collapse, manual_override
│                                        gera incident report + recovery_requirements
│
└── Q-8  LiveExecutionReplayEngine ────  replay deterministico por execucao
                                         campos: signal_context, indicator_snapshot,
                                                 orderbook_context, execution_timeline,
                                                 deviation_analysis
                                         scores: replay_fidelity_score, execution_correctness
                                         classification: normal|elevated|anomalous|critical
```

---

## 3. Modulos Criados

| Arquivo | FASE | Classe Principal | Scores/Outputs |
|---|---|---|---|
| `micro_live_execution_controller.py` | Q-1 | `MicroLiveExecutionController` | validate_live_trade(), authorize_execution(), live_state |
| `live_execution_auditor.py` | Q-2 | `LiveExecutionAuditor` | execution_quality_score, ExecutionRecord |
| `autonomous_live_guardian.py` | Q-3 | `AutonomousLiveGuardian` | guardian_state, emergency_level, contraction_multiplier |
| `paper_vs_live_divergence_engine.py` | Q-4 | `PaperVsLiveDivergenceEngine` | divergence_score, live_consistency_score, execution_alignment_score |
| `live_capital_preservation_engine.py` | Q-5 | `LiveCapitalPreservationEngine` | trading_allowed, approved_size_multiplier, capital_frozen |
| `live_readiness_revalidation_engine.py` | Q-6 | `LiveReadinessRevalidationEngine` | continuous_live_readiness_score, readiness_status |
| `autonomous_rollback_engine.py` | Q-7 | `AutonomousRollbackEngine` | rollback_executed, trigger_type, recovery_requirements |
| `live_execution_replay_engine.py` | Q-8 | `LiveExecutionReplayEngine` | replay_fidelity_score, execution_correctness, deviation_classification |
| `autonomous_live_governance.py` | Q-9 | `AutonomousLiveGovernance` | live_governance_score, operational_confidence, autonomous_live_approval |
| `api/live_metrics.py` | Q-10 | — | 14 metricas Prometheus |

---

## 4. Live State Machine (Q-1)

```
paper ──activate_live()──→ live_micro ──emergency_freeze()──→ live_frozen
  ↑                            │                                    │
  └──transition_to_paper()─────┘←──rollback_triggered───────────────┘
                                         (autonomo)
live_rollback (estado transitorio durante rollback gracioso)
```

**Hard limits inegociaveis (Q-1):**

| Parametro | Valor |
|---|---|
| MAX_CAPITAL_LIVE_PCT | 1.0% do capital total |
| MAX_RISK_PER_TRADE_PCT | 0.25% por trade |
| MIN_GOVERNANCE_HEALTH | 65 |
| MIN_READINESS_SCORE | 75 |
| MAX_RISK_SCORE | 50 |

---

## 5. Guardian — Niveis de Emergencia

| Level | Estado | Contraction | Condicao |
|---|---|---|---|
| 0 | NORMAL | 100% | Sem deteccoes |
| 0 | MONITORING | 100% | 1+ indicadores de atencao |
| 1 | CONTRACTING | 60% | loss_sequence OU hit_rate_degradation OU drawdown_acceleration |
| 2 | CONTRACTING | 35% | losses>=5 OU (hit_rate_crit AND drawdown_accel_crit) |
| 3 | FROZEN | 0% | 3+ deteccoes simultaneas |
| 4 | ROLLBACK | 15% | losses>=5 AND hit_rate<35% |
| 5 | SHUTDOWN | 0% | (reservado — shutdown completo) |

---

## 6. Capital Preservation — Hard Limits (Q-5)

| Condicao | Acao |
|---|---|
| 2 losses consecutivos | contracao 50% do tamanho |
| 3 losses consecutivos | contracao 25% do tamanho |
| 4+ losses consecutivos | capital_freeze (sem novas ordens) |
| daily_drawdown >= 2% | daily_halt (parada do dia) |
| weekly_drawdown >= 4% | weekly_halt (parada da semana) |
| exposure > 1% capital | rejeicao de ordem |
| trade > 0.25% capital | clipping automatico |

---

## 7. Readiness Revalidation — Status Thresholds (Q-6)

| Status | Score | Acao |
|---|---|---|
| GREEN | >= 75 | Operacao normal |
| YELLOW | >= 55 | Monitoramento intensivo |
| ORANGE | >= 40 | Contracao automatica + alerta |
| RED | < 40 | Rollback automatico recomendado |

**Penalidades no score:**

| Input | Penalidade Maxima |
|---|---|
| governance_health < 65 | -25 pts |
| execution_quality < 60 | -20 pts |
| guardian_state = ROLLBACK | -30 pts |
| divergence_score > 50 | -15 pts |
| capital_preserved = False | -20 pts |

---

## 8. Rollback Engine — Triggers (Q-7)

| Severity | Trigger | Condicao | Manual Review |
|---|---|---|---|
| 1 | guardian_rollback | Guardian emitiu ROLLBACK | SIM |
| 2 | readiness_red | LiveReadiness = RED | SIM |
| 3 | capital_halt | Capital engine suspendeu trading | nao |
| 4 | exchange_degradation | Auditor detectou exchange_degradation | nao |
| 5 | divergence_critical | divergence_score > 70 | nao |
| 6 | governance_collapse | governance_health < 50 | nao |
| 7 | manual_override | CLI --trigger manual | nao |

**Recovery requirements (pos-rollback):**

- governance_health >= 70 por 2+ ciclos
- execution_quality >= 70
- readiness_score >= 80
- zero deteccoes criticas por 3+ ciclos
- revisao manual obrigatoria para severity 1 ou 2

---

## 9. Replay Engine — Deviation Classification (Q-8)

| Classificacao | Slippage | Significado |
|---|---|---|
| normal | < 5 bps | Execucao dentro do esperado |
| elevated | 5-10 bps | Atencao, monitorar |
| anomalous | 10-20 bps | Investigar microestrutura |
| critical | >= 20 bps | Possivel problema de exchange |

**Fidelity score formula:**
```
fidelity = timing×0.25 + fill×0.30 + slippage×0.30 + context×0.15
```

---

## 10. Live Governance Score Formula (Q-9)

```
live_governance_score =
  readiness_score   × 0.25
  guardian_score    × 0.20
  capital_safety    × 0.20
  exec_quality      × 0.15
  (100-divergence)  × 0.10
  replay_fidelity   × 0.10
```

**autonomous_live_approval = True** quando:
- live_governance_score >= 55
- capital_safety_score >= 60
- guardian_state NOT IN {FROZEN, ROLLBACK}
- trading_allowed = True
- rollback_executed = False (neste ciclo)
- readiness_status != RED

---

## 11. Metricas Prometheus (Q-10 — api/live_metrics.py)

| Metrica | Tipo | Origem |
|---|---|---|
| `live_governance_score` | Gauge | AutonomousLiveGovernance |
| `execution_quality_score` | Gauge | LiveExecutionAuditor |
| `divergence_score` | Gauge | PaperVsLiveDivergenceEngine |
| `live_consistency_score` | Gauge | PaperVsLiveDivergenceEngine |
| `guardian_emergency_level` | Gauge | AutonomousLiveGuardian |
| `rollback_events_total` | Counter[trigger] | AutonomousRollbackEngine |
| `live_drawdown_pct` | Gauge | LiveCapitalPreservationEngine |
| `live_capital_exposure_pct` | Gauge | LiveCapitalPreservationEngine |
| `execution_latency_ms` | Gauge | LiveExecutionAuditor |
| `live_slippage_bps` | Gauge | LiveExecutionAuditor |
| `autonomous_freeze_state` | Gauge | MicroLiveExecutionController |
| `live_readiness_score` | Gauge | LiveReadinessRevalidationEngine |
| `exchange_instability_score` | Gauge | AutonomousLiveGuardian |
| `contraction_multiplier` | Gauge | AutonomousLiveGuardian |

---

## 12. Persistencia

| Arquivo | Quem Escreve | Campos-chave |
|---|---|---|
| `data/live_execution_state.json` | MicroLiveExecutionController | live_state, entered_live_at, frozen_at |
| `data/live_execution_controller_log.jsonl` | MicroLiveExecutionController | validation_id, allowed, rejection_reason |
| `data/live_execution_audit_log.jsonl` | LiveExecutionAuditor | record_id, mode, slippage_bps, fill_rate |
| `data/live_execution_audit_summary.jsonl` | LiveExecutionAuditor | execution_quality_score, exchange_degradation |
| `data/live_guardian_log.jsonl` | AutonomousLiveGuardian | guardian_state, emergency_level, contraction_multiplier |
| `data/paper_vs_live_divergence_log.jsonl` | PaperVsLiveDivergenceEngine | divergence_score, slippage_gap_bps |
| `data/live_capital_preservation_log.jsonl` | LiveCapitalPreservationEngine | trading_allowed, consecutive_losses, daily_drawdown_pct |
| `data/live_readiness_revalidation_log.jsonl` | LiveReadinessRevalidationEngine | continuous_live_readiness_score, readiness_status |
| `data/autonomous_rollback_log.jsonl` | AutonomousRollbackEngine | rollback_executed, trigger_type, triggers_fired |
| `data/live_incident_reports.jsonl` | AutonomousRollbackEngine | incident_id, recovery_requirements, post_mortem_reference |
| `data/live_execution_replay_log.jsonl` | LiveExecutionReplayEngine | replay_id, replay_fidelity_score, deviation_classification |
| `data/live_governance_history.jsonl` | AutonomousLiveGovernance | cycle_id, live_governance_score, autonomous_live_approval |
| `data/live_governance_summary.jsonl` | AutonomousLiveGovernance | todas as scores agregadas por ciclo |

---

## 13. CLIs Disponiveis

```bash
# Q-1: Controller
python -m domains.crypto_coin.research.micro_live_execution_controller --status
python -m domains.crypto_coin.research.micro_live_execution_controller --activate
python -m domains.crypto_coin.research.micro_live_execution_controller --validate --json
python -m domains.crypto_coin.research.micro_live_execution_controller --freeze
python -m domains.crypto_coin.research.micro_live_execution_controller --to-paper

# Q-2: Auditor
python -m domains.crypto_coin.research.live_execution_auditor
python -m domains.crypto_coin.research.live_execution_auditor --record
python -m domains.crypto_coin.research.live_execution_auditor --json

# Q-3: Guardian
python -m domains.crypto_coin.research.autonomous_live_guardian
python -m domains.crypto_coin.research.autonomous_live_guardian --json

# Q-4: Divergence
python -m domains.crypto_coin.research.paper_vs_live_divergence_engine
python -m domains.crypto_coin.research.paper_vs_live_divergence_engine --json

# Q-5: Capital
python -m domains.crypto_coin.research.live_capital_preservation_engine
python -m domains.crypto_coin.research.live_capital_preservation_engine --exposure 50 --trade 5

# Q-6: Revalidation
python -m domains.crypto_coin.research.live_readiness_revalidation_engine
python -m domains.crypto_coin.research.live_readiness_revalidation_engine --json

# Q-7: Rollback
python -m domains.crypto_coin.research.autonomous_rollback_engine --status
python -m domains.crypto_coin.research.autonomous_rollback_engine --trigger manual

# Q-8: Replay
python -m domains.crypto_coin.research.live_execution_replay_engine
python -m domains.crypto_coin.research.live_execution_replay_engine --record

# Q-9: Governance (orchestrator)
python -m domains.crypto_coin.research.autonomous_live_governance --run
python -m domains.crypto_coin.research.autonomous_live_governance --run-n 3
python -m domains.crypto_coin.research.autonomous_live_governance --status
```

---

## 14. Grafana Dashboard

`grafana/dashboards/crypto_live_governance.json`
- uid: `crypto-live-governance-q`
- 10 secoes: Live Governance, Capital Protection, Execution Quality, Slippage Analysis,
  Paper vs Live Divergence, Guardian State, Rollback Events, Exchange Health,
  Readiness Revalidation, Live Stability
- Refresh: 30s | Janela: last 3h

---

## 15. Gaps Identificados (pos-Phase Q)

| Gap | Prioridade | Descricao |
|---|---|---|
| Q-GAP-01 | Alta | `MicroLiveExecutionController` sem integracao com exchange real — requer Binance Testnet |
| Q-GAP-02 | Alta | `LiveExecutionAuditor` precisa de dados reais de fill/latencia — hoje usa dados inseridos manualmente |
| Q-GAP-03 | Alta | `AutonomousLiveGovernance` nao esta wired como scheduled task (cron) |
| Q-GAP-04 | Media | `LiveCapitalPreservationEngine` total_capital_usd hardcoded — deve vir de portfolio real |
| Q-GAP-05 | Media | `LiveExecutionReplayEngine` indicator_snapshot estimado — requer dados de mercado reais |
| Q-GAP-06 | Media | Alertas Grafana nao configurados para guardian>=CONTRACTING e rollback_events>0 |
| Q-GAP-07 | Baixa | `PaperVsLiveDivergenceEngine` sem baseline de paper real — requer paper trading paralelo |

---

## 16. Fluxo Operacional Live

```
1. Prerequisito: MicroLiveReadinessEngine.approved_for_micro_live = True (Phase P)

2. Ativacao:
   MicroLiveExecutionController.activate_live()
   → live_state: paper → live_micro

3. Por trade:
   validate_live_trade(confidence, risk_score, exposure, gov_health, readiness)
   → TradeValidationResult.allowed = True/False
   authorize_execution(result) → bool
   enforce_micro_capital(requested_usd) → float (clipped)

4. Pos-trade:
   LiveExecutionAuditor.record_execution(ExecutionRecord.build(...))

5. Ciclo de governanca (a cada N minutos):
   AutonomousLiveGovernance.run_once()
   → agrega todos os modulos Q
   → autonomous_live_approval = True/False
   → rollback_executed (se necessario)

6. Rollback automatico:
   AutonomousRollbackEngine detecta trigger
   → MicroLiveExecutionController.transition_to_paper()
   → incident report persistido em data/live_incident_reports.jsonl

7. Reativacao (apos recovery):
   Validar recovery_requirements
   → revisao manual (se severity <= 2)
   → activate_live() novamente
```

---

## 17. Maturidade Quantitativa Atual

```
L1  Dados brutos
L2  Pipeline funcional
L3  Analytics + Prometheus
L4  Research + backtesting
L5  Intelligence layer
L6  Autonomous recommendations
L7  Autonomous governance (Phase O)
L8  Autonomous validation + micro-live readiness (Phase P)
L8+ Micro-live execution + capital-protected autonomy (Phase Q) <- ATUAL
```

Sistema pronto para primeira execucao live controlada com capital minimo ($50-200),
sujeito a aprovacao formal do MicroLiveReadinessEngine e ativacao manual explicita.

---

*Phase Q implementada em modo autonomo supervisionado. Capital PAPER ONLY ate ativacao explicita.*
