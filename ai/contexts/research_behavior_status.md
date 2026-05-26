# Research & Behavior Status — Poupi Platform

> Last updated: 2026-05-17 (Phase S — Runtime Burn-In, Observability Validation & Data Reliability)
> Full detail: `docs/RESEARCH_AND_BEHAVIOR_MATRIX.md`

## Estado Atual por Componente

### Trilha A — Poupi Baby

| Componente | Status | Arquivo |
|---|---|---|
| Seed de usuários internos | ✅ Script criado — pendente execução | `src/seed/seed-internal-users.ts` |
| BehaviorTrackingService | ✅ Implementado — precisa ser integrado aos controllers | `src/analytics/behavior-tracking.service.ts` |
| AlertQualityService | ✅ Implementado — sem endpoint admin ainda | `src/analytics/alert-quality.service.ts` |
| behaviorEvents counter | ✅ Adicionado ao MetricsService | `src/metrics/metrics.service.ts` |
| DealScore por categoria | ✅ `getByCategory()` + `GET /deal-score/category/:category` | `src/deal-score/deal-score.service.ts` |
| Grafana dashboard | ✅ 14 painéis provisionados | `grafana/provisioning/dashboards/poupi_baby.json` |
| Tracking token nos emails | ❌ G-H-02 persiste — não embutido | `notifications/notifications.service.ts` |

### Trilha B — Crypto Research

| Componente | Status | Arquivo |
|---|---|---|
| ExperimentTracker | ✅ JSONL persistence, compare, best, summary, CLI | `research/experiment_tracker.py` |
| StrategyRegistry | ✅ YAML + interface Python, 4 estratégias | `research/strategy_registry.yaml` + `.py` |
| sweep_runner | ✅ Grid search + batch replay + auto-record | `research/sweep_runner.py` |
| regime_analytics | ✅ Win/loss por regime, volatility buckets, transições | `analytics/regime_analytics.py` |
| OHLCV integrity (extendido) | ✅ + drift, flat candles, integrity_score, Prometheus wired | `analytics/ohlcv_integrity.py` |
| db_replay Prometheus | ✅ backtest_runs_total + duration + candles wired | `backtesting/db_replay.py` |

## O que está PRONTO para uso

### Poupi Baby
- `npx ts-node src/seed/seed-internal-users.ts` — cria usuários internos com watchlists e alertas
- `GET /deal-score/category/Fraldas?minScore=60` — oportunidades por categoria
- `BehaviorTrackingService.alertViewed(userId, alertId, productId)` — rastrear engajamento
- `AlertQualityService.getSummary(14)` — relatório de qualidade de alertas últimos 14 dias
- Grafana: montar container com `grafana/provisioning/` para ver os 14 painéis

### Crypto
- `python -m domains.crypto_coin.research.experiment_tracker --compare --strategy trend_following`
- `python -m domains.crypto_coin.research.strategy_registry --list`
- `python -m domains.crypto_coin.research.sweep_runner --strategy trend_following --symbol BTC/USDT --tf 15m --sweep rsi_oversold:25,30,35`
- `python -m domains.crypto_coin.analytics.regime_analytics --symbol BTC/USDT --tf 15m --days 90`
- `replay_from_db(db, symbol, tf, days)` agora incrementa `backtest_runs_total` e `backtest_duration_seconds`
- `check_integrity(db, symbol, tf)` agora incrementa `ohlcv_integrity_checks_total`

## Adicionado em Phase S

### Trilha B — Crypto Research (Runtime Burn-In, Observability Validation & Data Reliability — L9 Stabilization)

| Componente | Score(s)/Output | Arquivo |
|---|---|---|
| `RuntimeBurninEngine` | burnin_stability_score, runtime_burnin_score, long_session_integrity_score | `research/runtime_burnin_engine.py` |
| `MetricsIntegrityValidator` | metrics_integrity_score, metrics_continuity_score, observability_health_score | `research/metrics_integrity_validator.py` |
| `GrafanaDashboardValidator` | dashboard_integrity_score, panel_health_score, visualization_consistency_score | `research/grafana_dashboard_validator.py` |
| `CollectorReliabilityEngine` | collector_reliability_score, normalization_integrity_score, data_freshness_score | `research/collector_reliability_engine.py` |
| `ReplayIntegrityBurninValidator` | replay_burnin_score, replay_continuity_score, replay_consistency_score | `research/replay_integrity_burnin_validator.py` |
| `IncidentNoiseReductionEngine` | incident_signal_quality_score, alert_precision_score, operational_noise_score | `research/incident_noise_reduction_engine.py` |
| `ColdStartResilienceValidator` | cold_start_resilience_score, grade (A-F) | `research/cold_start_resilience_validator.py` |
| `OperationalDriftAnalyzer` | operational_drift_score, runtime_consistency_trend, stability_trend_score | `research/operational_drift_analyzer.py` |
| `AutonomousRuntimeStabilityOrchestrator` | runtime_stability_score, observability_readiness_score, burnin_readiness_score, burnin_operational_maturity_score | `research/autonomous_runtime_stability_orchestrator.py` |
| `api/burnin_metrics.py` | 33 métricas Prometheus Phase S (29G+4C) | `api/burnin_metrics.py` |

**CLIs Phase S:**
```bash
python -m domains.crypto_coin.research.runtime_burnin_engine
python -m domains.crypto_coin.research.metrics_integrity_validator
python -m domains.crypto_coin.research.grafana_dashboard_validator
python -m domains.crypto_coin.research.collector_reliability_engine
python -m domains.crypto_coin.research.replay_integrity_burnin_validator
python -m domains.crypto_coin.research.incident_noise_reduction_engine
python -m domains.crypto_coin.research.cold_start_resilience_validator
python -m domains.crypto_coin.research.operational_drift_analyzer
python -m domains.crypto_coin.research.autonomous_runtime_stability_orchestrator --summary
python -m domains.crypto_coin.research.autonomous_runtime_stability_orchestrator --json
```

**Persistência Phase S:**

| Arquivo | Conteúdo |
|---|---|
| `data/runtime_burnin_log.jsonl` | Ciclos burn-in engine (S-1) |
| `data/metrics_integrity_log.jsonl` | Validações de freshness de métricas (S-2) |
| `data/dashboard_validation_log.jsonl` | Validações estruturais de dashboards (S-3) |
| `data/collector_reliability_log.jsonl` | Freshness e parse health de collectors (S-4) |
| `data/replay_burnin_log.jsonl` | Continuidade e gaps de sessões replay (S-5) |
| `data/incident_noise_log.jsonl` | Análise de ruído de alertas (S-6) |
| `data/cold_start_validation_log.jsonl` | Resultados de validação de cold start (S-7) |
| `data/operational_drift_log.jsonl` | Drift por dimensão operacional (S-8) |
| `data/runtime_stability_log.jsonl` | Ciclos completos do orquestrador S-9 |
| `data/runtime_stability_summary.jsonl` | Último sumário (overwrite por ciclo) |

## Adicionado em Phase R

### Trilha B — Crypto Research (Autonomous Runtime Governance & Production Hardening — L9)

| Componente | Score(s)/Output | Arquivo |
|---|---|---|
| `AutonomousStartupManager` | startup_health_score, startup_integrity_score, startup_recovery_state | `research/autonomous_startup_manager.py` |
| `OperationalStateRestorationEngine` | restoration_integrity_score, state_consistency_score, replay_recovery_score | `research/operational_state_restoration_engine.py` |
| `AutonomousServiceWatchdog` | watchdog_health_score, loop_integrity_score, runtime_anomaly_score | `research/autonomous_service_watchdog.py` |
| `LongRunningStabilityEngine` | runtime_health_score, operational_decay_score, long_running_stability_score, runtime_consistency_score | `research/long_running_stability_engine.py` |
| `DeploymentSafetyValidator` | deployment_safety_score, migration_integrity_score, rollback_risk_score, compatibility_score | `research/deployment_safety_validator.py` |
| `AutonomousIncidentManager` | incident_severity_score, incident_frequency_score, operational_risk_score | `research/autonomous_incident_manager.py` |
| `OperationalRecoveryEngine` | recovery_success_rate, recovery_integrity_score, recovery_duration_ms | `research/operational_recovery_engine.py` |
| `AutonomousRuntimeGovernance` | runtime_governance_score, operational_resilience_score, production_readiness_score | `research/autonomous_runtime_governance.py` |
| `ProductionReadinessClassifier` | readiness_confidence, operational_maturity_score, classification | `research/production_readiness_classifier.py` |
| `api/runtime_metrics.py` | 31 métricas Prometheus Phase R | `api/runtime_metrics.py` |

**CLIs Phase R:**
```bash
python -m domains.crypto_coin.research.autonomous_startup_manager --json
python -m domains.crypto_coin.research.autonomous_startup_manager --dry-run
python -m domains.crypto_coin.research.operational_state_restoration_engine --persist
python -m domains.crypto_coin.research.operational_state_restoration_engine --restore --json
python -m domains.crypto_coin.research.autonomous_service_watchdog --json
python -m domains.crypto_coin.research.long_running_stability_engine --json
python -m domains.crypto_coin.research.deployment_safety_validator --json
python -m domains.crypto_coin.research.autonomous_incident_manager --summary --json
python -m domains.crypto_coin.research.autonomous_incident_manager --create --subsystem api --severity WARNING --root-cause "latency elevated"
python -m domains.crypto_coin.research.autonomous_incident_manager --auto-resolve
python -m domains.crypto_coin.research.operational_recovery_engine --json --trigger manual
python -m domains.crypto_coin.research.operational_recovery_engine --actions restore_state revalidate_readiness
python -m domains.crypto_coin.research.autonomous_runtime_governance --run --json
python -m domains.crypto_coin.research.autonomous_runtime_governance --status
python -m domains.crypto_coin.research.production_readiness_classifier --json
```

**Persistência Phase R:**

| Arquivo | Conteúdo |
|---|---|
| `data/runtime_state.json` | Estado de startup: fase, scores, session_start |
| `data/operational_state.json` | Estado operacional completo (schema v1.0) |
| `data/startup_log.jsonl` | Relatórios de startup por boot |
| `data/state_restoration_log.jsonl` | Log de restaurações de estado |
| `data/watchdog_log.jsonl` | Health checks de todos os serviços |
| `data/stability_log.jsonl` | Scores de estabilidade long-running |
| `data/deployment_validation_log.jsonl` | Resultados de validação pré-deploy |
| `data/incident_log.jsonl` | Log append-only de todos os incidentes |
| `data/active_incidents.json` | Índice mutável de incidentes ativos |
| `data/recovery_log.jsonl` | Relatórios de recovery controlado |
| `data/recovery_markers.json` | Markers de ações de recovery pendentes |
| `data/runtime_governance_log.jsonl` | Ciclos completos do orquestrador R-8 |
| `data/runtime_governance_summary.jsonl` | Sumários do orquestrador (lightweight) |
| `data/production_readiness_log.jsonl` | Classificações de readiness por ciclo |

**Env vars Phase R:**
```env
BOT_AUTO_START=true
TRADING_MODE=paper
ALLOW_LIVE_AUTO_ACTIVATION=false
REQUIRE_MANUAL_LIVE_CONFIRMATION=true
```

## Adicionado em Phase Q

### Trilha B — Crypto Research (Micro-Live Execution & Capital-Protected Autonomy — L8+)

| Componente | Score(s)/Output | Arquivo |
|---|---|---|
| `MicroLiveExecutionController` | validate_live_trade(), authorize_execution(), live_state | `research/micro_live_execution_controller.py` |
| `LiveExecutionAuditor` | execution_quality_score, ExecutionRecord | `research/live_execution_auditor.py` |
| `AutonomousLiveGuardian` | guardian_state, emergency_level, contraction_multiplier | `research/autonomous_live_guardian.py` |
| `PaperVsLiveDivergenceEngine` | divergence_score, live_consistency_score, execution_alignment_score | `research/paper_vs_live_divergence_engine.py` |
| `LiveCapitalPreservationEngine` | trading_allowed, approved_size_multiplier, capital_frozen | `research/live_capital_preservation_engine.py` |
| `LiveReadinessRevalidationEngine` | continuous_live_readiness_score, readiness_status | `research/live_readiness_revalidation_engine.py` |
| `AutonomousRollbackEngine` | rollback_executed, trigger_type, recovery_requirements | `research/autonomous_rollback_engine.py` |
| `LiveExecutionReplayEngine` | replay_fidelity_score, execution_correctness, deviation_classification | `research/live_execution_replay_engine.py` |
| `AutonomousLiveGovernance` | live_governance_score, autonomous_live_approval, operational_confidence | `research/autonomous_live_governance.py` |

**CLIs Phase Q:**
```bash
python -m domains.crypto_coin.research.micro_live_execution_controller --status
python -m domains.crypto_coin.research.micro_live_execution_controller --activate
python -m domains.crypto_coin.research.micro_live_execution_controller --validate --json
python -m domains.crypto_coin.research.live_execution_auditor --record
python -m domains.crypto_coin.research.live_execution_auditor --json
python -m domains.crypto_coin.research.autonomous_live_guardian --json
python -m domains.crypto_coin.research.paper_vs_live_divergence_engine --json
python -m domains.crypto_coin.research.live_capital_preservation_engine
python -m domains.crypto_coin.research.live_readiness_revalidation_engine
python -m domains.crypto_coin.research.autonomous_rollback_engine --status
python -m domains.crypto_coin.research.autonomous_rollback_engine --trigger manual
python -m domains.crypto_coin.research.live_execution_replay_engine
python -m domains.crypto_coin.research.autonomous_live_governance --run
python -m domains.crypto_coin.research.autonomous_live_governance --run-n 3
python -m domains.crypto_coin.research.autonomous_live_governance --status
```

**Persistência Phase Q:**

| Arquivo | Conteúdo |
|---|---|
| `data/live_execution_state.json` | Estado atual do controller (live_state, timestamps) |
| `data/live_execution_controller_log.jsonl` | Log de validacoes e eventos de estado |
| `data/live_execution_audit_log.jsonl` | Registros de execucao (paper e live) |
| `data/live_execution_audit_summary.jsonl` | Sumarizacoes de auditoria por janela |
| `data/live_guardian_log.jsonl` | Estado do guardian por ciclo |
| `data/paper_vs_live_divergence_log.jsonl` | Divergencias paper vs live |
| `data/live_capital_preservation_log.jsonl` | Estado de preservacao de capital |
| `data/live_readiness_revalidation_log.jsonl` | Score de prontidao continua |
| `data/autonomous_rollback_log.jsonl` | Decisoes de rollback por ciclo |
| `data/live_incident_reports.jsonl` | Incident reports detalhados |
| `data/live_execution_replay_log.jsonl` | Replays deterministicos por execucao |
| `data/live_governance_history.jsonl` | Ciclos completos de governanca live |
| `data/live_governance_summary.jsonl` | Sumarizacoes de governanca live |

## Adicionado em Phase P

### Trilha B — Crypto Research (Autonomous Validation & Micro-Live Readiness — L8)

| Componente | Score(s) | Arquivo |
|---|---|---|
| `AutonomousBehaviorAuditor` | system_autonomy_score, runaway_risk_score, operational_stability_score | `research/autonomous_behavior_audit.py` |
| `AutonomousStabilityIntelligence` | autonomy_stability_score, allocation_stability_score, governance_consistency_score | `research/autonomous_stability_intelligence.py` |
| `CapitalPreservationValidator` | capital_survival_score, preservation_efficiency_score, drawdown_protection_score | `research/capital_preservation_validator.py` |
| `CatastrophicSimulationEngine` | catastrophic_survival_score, autonomous_reaction_score, scenario_resilience_scores | `research/catastrophic_simulation_engine.py` |
| `MicroLiveReadinessEngine` | live_readiness_score, execution_reliability_score, slippage_quality_score | `research/micro_live_readiness_engine.py` |
| `SafeAutonomousConstraints` | all_constraints_passed, emergency_contraction, max_allowed_total_exposure | `research/safe_autonomous_constraints.py` |
| `ExecutionSimulationEngine` | execution_realism_score, fill_quality_score, latency_impact_score | `research/execution_simulation_engine.py` |
| `GovernanceDriftIntelligence` | governance_drift_score, adaptation_quality_score, autonomous_balance_score | `research/governance_drift_intelligence.py` |
| `AutonomousValidationLoop` | validation_health_score, live_readiness_score, approved_for_micro_live | `research/autonomous_validation_loop.py` |

**CLIs Phase P:**
```bash
python -m domains.crypto_coin.research.autonomous_behavior_audit --json
python -m domains.crypto_coin.research.autonomous_stability_intelligence --json
python -m domains.crypto_coin.research.capital_preservation_validator --json
python -m domains.crypto_coin.research.catastrophic_simulation_engine
python -m domains.crypto_coin.research.catastrophic_simulation_engine --scenario flash_crash
python -m domains.crypto_coin.research.micro_live_readiness_engine --json
python -m domains.crypto_coin.research.safe_autonomous_constraints --simulate
python -m domains.crypto_coin.research.execution_simulation_engine --symbol BTC/USDT --size 100 --n 200
python -m domains.crypto_coin.research.governance_drift_intelligence --json
python -m domains.crypto_coin.research.autonomous_validation_loop --once
python -m domains.crypto_coin.research.autonomous_validation_loop --n 5
```

**Persistência Phase P:**

| Arquivo | Conteúdo |
|---|---|
| `data/behavior_audit_log.jsonl` | Achados de auditoria de comportamento |
| `data/stability_intelligence_log.jsonl` | Scores de estabilidade por ciclo |
| `data/capital_preservation_log.jsonl` | Resultados de validação de preservação |
| `data/catastrophic_simulation_log.jsonl` | Resultados por cenário catastrófico |
| `data/live_readiness_log.jsonl` | Gates e aprovação para micro-live |
| `data/safe_constraints_log.jsonl` | Violações e contrações de emergência |
| `data/execution_simulation_log.jsonl` | Monte Carlo de execução por regime |
| `data/governance_drift_log.jsonl` | Deriva de qualidade de governança |
| `data/validation_loop_history.jsonl` | Ciclos completos de validação |

## Adicionado em Phase O

### Trilha B — Crypto Research (Fully Autonomous Quant Governance — L7)

| Componente | Score(s) | Arquivo |
|---|---|---|
| `StrategyActivationEngine` | activation_state, strategy_trust_score | `research/strategy_activation_engine.py` |
| `AutonomousExposureControl` | emergency_exposure_score, survival_mode_score, volatility_protection_score | `research/autonomous_exposure_control.py` |
| `AutonomousPortfolioGovernor` | portfolio_survival_score, adaptive_resilience_score, portfolio_stress_score | `research/adaptive_quant_intelligence.py` |
| `MarketSurvivalIntelligence` | market_survival_score, instability_risk_score, systemic_risk_score | `research/market_survival_intelligence.py` |
| `AutonomousResearchEvolution` | optimization_efficiency, research_gaps | `research/autonomous_research_loop.py` |
| `SelfHealingIntelligence` | infrastructure_health_score, recovery_confidence_score, self_healing_score | `research/self_healing_intelligence.py` |
| `AutonomousExecutionIntelligence` | execution_confidence_score, sizing_quality_score, capital_efficiency_score | `research/autonomous_execution_intelligence.py` |
| `AdaptiveRiskIntelligence` | adaptive_risk_score, contagion_risk_score, hidden_fragility_score | `research/adaptive_risk_intelligence.py` |
| `MetaOptimizationIntelligence` | optimization_efficiency_score, computational_priority_score, adaptive_efficiency_score | `research/meta_optimization_intelligence.py` |
| `AutonomousGovernance` | governance_health_score, autonomy_confidence_score, system_resilience_score | `research/autonomous_governance.py` |

**CLIs Phase O:**
```bash
python -m domains.crypto_coin.research.strategy_activation_engine --all
python -m domains.crypto_coin.research.autonomous_exposure_control --all
python -m domains.crypto_coin.research.market_survival_intelligence --json
python -m domains.crypto_coin.research.self_healing_intelligence --heal
python -m domains.crypto_coin.research.autonomous_execution_intelligence --all
python -m domains.crypto_coin.research.adaptive_risk_intelligence --json
python -m domains.crypto_coin.research.meta_optimization_intelligence --json
python -m domains.crypto_coin.research.autonomous_governance --all --heal
```

**Persistência Phase O:**

| Arquivo | Conteúdo |
|---|---|
| `data/strategy_activation_log.jsonl` | ActivationEvents com lineage UUID |
| `data/strategy_activation_state.json` | Estado atual de cada estratégia |
| `data/exposure_control_log.jsonl` | Decisões de exposure por ciclo |
| `data/survival_history.jsonl` | Histórico de market survival |
| `data/self_healing_log.jsonl` | Log de diagnóstico de infra |
| `data/quarantined_experiments.json` | run_ids em quarentena (nunca deletados) |
| `data/execution_intelligence_log.jsonl` | Decisões de execução com reasoning |
| `data/adaptive_risk_log.jsonl` | Histórico de risco adaptativo |
| `data/meta_optimization_log.jsonl` | Histórico de eficiência de otimização |
| `data/governance_history.jsonl` | Ciclos completos de governança |

## Adicionado em Phase N

### Trilha B — Crypto Research (Autonomous Adaptive Quant Evolution)

| Componente | Status | Arquivo |
|---|---|---|
| `MarketDriftIntelligence` | ✅ market_drift_score, edge_decay_score, regime_shift_score, volatility_shift_score | `research/market_drift_intelligence.py` |
| `DriftHistoryReader` | ✅ persistência JSONL + análise de tendência histórica | `research/market_drift_intelligence.py` |
| `StrategyLifecycleEngine` | ✅ lifecycle_state, promotion_score, retirement_score, recovery_score | `research/strategy_lifecycle.py` |
| `AdaptiveExposureIntelligence` | ✅ adaptive_exposure_score, stress_exposure_score, regime_exposure_score | `research/adaptive_exposure_intelligence.py` |
| `MetaStrategyIntelligence` | ✅ correlation_matrix, hedge_compatibility_score, diversification_synergy_score | `research/meta_strategy_intelligence.py` |
| `ResearchPrioritizer` | ✅ research/replay/validation priority scores, fila priorizada | `research/research_prioritizer.py` |
| `ParameterIntelligence` | ✅ parameter_stability_score, range_quality_score, adaptive_parameter_priority | `research/parameter_intelligence.py` |
| `AdaptivePortfolioEvolution` | ✅ portfolio_resilience_score, adaptive_diversification_score, portfolio_drift_score | `research/adaptive_quant_intelligence.py` |
| `QuantRecommendationEngineV2` | ✅ lifecycle + drift + conflicting pairs + Phase M base | `research/adaptive_quant_intelligence.py` |
| `AutonomousResearchScheduler` | ✅ loop semi-autônomo 8 fases + lineage JSONL + Prometheus | `research/autonomous_research_loop.py` |
| 9 novas métricas Prometheus | ✅ market_drift, edge_decay, retirements, promotions, exposure, research_priority, param_stability, resilience, autonomous_recs | `api/metrics.py` |
| Dashboard Grafana Phase N | ✅ 7 rows, 20 painéis (drift, lifecycle, exposure, portfolio, research, loop, composite) | `grafana/dashboards/crypto_autonomous_quant.json` |

## Adicionado em Phase M

### Trilha A — Poupi Baby (Adaptive Intelligence)

| Componente | Status | Arquivo |
|---|---|---|
| `PreferenceLearningService` | ✅ preference/affinity/engagement/fatigue scores por usuário e frota | `analytics/preference-learning.service.ts` |
| `AdaptiveDistributionService` | ✅ timing_score, category_relevance, marketplace_relevance, posting_readiness | `telegram-groups/adaptive-distribution.service.ts` |
| `OpportunityIntelligenceService` | ✅ opportunity_quality_score, expected_ctr_score, behavioral_fit_score | `deal-score/opportunity-intelligence.service.ts` |
| `FeedbackLoopService` | ✅ runCycle(), getLoopHealth(), insight generation | `analytics/feedback-loop.service.ts` |
| `RecommendationService` | ✅ IntelligenceSummary com recommendations priorizadas | `analytics/recommendation.service.ts` |
| `BehaviorQualityService` | ✅ behavior_health_score, engagement_decay, distribution_stability | `analytics/behavior-quality.service.ts` |
| `ContentIntelligenceService` | ✅ title_length, savings_impact, deal_tier_distribution, content_quality | `analytics/content-intelligence.service.ts` |
| 7 novas métricas Prometheus | ✅ adaptive_posting, timing, behavior_health, engagement_decay, stability, content_quality, feedback_loop_runs | `metrics/metrics.service.ts` |
| 6 novos endpoints admin | ✅ /intelligence/recommendations, /posting-readiness, /behavior-quality, /content, /feedback, /timing | `admin/admin.controller.ts` |

### Trilha B — Crypto Research (Adaptive Quant Intelligence)

| Componente | Status | Arquivo |
|---|---|---|
| `StrategyDegradationIntelligence` | ✅ degradation_score, health_score, stability_score, robustness_score | `research/strategy_degradation_intelligence.py` |
| `FragilityIntelligenceAnalyzer` | ✅ fragility_score, overfitting_score, replay_consistency, perturbation_sensitivity | `research/fragility_intelligence.py` |
| `RegimeAwareIntelligence` | ✅ regime_confidence_score, compatibility_matrix, adaptive_regime_ranking | `research/regime_aware_intelligence.py` |
| `AdaptiveAllocationEngine` | ✅ paper only, pesos por health_score, max 60%/min 5% | `research/adaptive_quant_intelligence.py` |
| `QuantRecommendationIntelligence` | ✅ recommendations por estratégia (retire/investigate/sweep/monitor) | `research/adaptive_quant_intelligence.py` |
| `AdaptivePortfolioIntelligence` | ✅ portfolio_health_score, diversification_quality, adaptive_portfolio_score | `research/adaptive_quant_intelligence.py` |
| `run_research_loop()` | ✅ iteração contínua: degradation→fragility→recommendations→portfolio | `research/adaptive_quant_intelligence.py` |
| 6 novas métricas Prometheus | ✅ degradation_score, health_score, fragility_score, overfitting_score, portfolio_health, research_loop_runs | `api/metrics.py` |

## Adicionado em Phase L

### Trilha A — Poupi Baby

| Componente | Status | Arquivo |
|---|---|---|
| Distribuição automática ativada | ✅ `TELEGRAM_GROUP_MANUAL_APPROVAL=false` | `.env` |
| Bug fix Boolean env parse | ✅ `!== 'false'` em publisher + trigger | `telegram-group-publisher.service.ts` |
| `N8nWebhookChannel` | ✅ POST com retry 3x, timeout 10s, nativo fetch | `n8n-webhook.channel.ts` |
| `DistributionChannelRegistry` | ✅ Dispatch paralelo para canais habilitados | `distribution-channel.registry.ts` |
| `SocialPayload` v1.1 | ✅ `mediaCaption` + `altText` adicionados | `social-payload.builder.ts` |
| `TelegramGroupCTRAnalyticsService` | ✅ CTR por hora/score/marketplace/categoria/janela/fadiga | `telegram-group-ctr-analytics.service.ts` |
| `DistributionQualityEngine` | ✅ Flood/repetição/fadiga detection; quality/spam/fatigue scores | `distribution-quality.engine.ts` |
| `GrowthAnalyticsService` | ✅ Velocity, efficiency, saturation, marketplace perf, health score | `analytics/growth-analytics.service.ts` |
| `DistributionScalabilitySpec` | ✅ Contratos multi-canal, maturity roadmap L3→L4→L5 | `distribution-scalability.spec.ts` |
| `GET /admin/telegram-groups/ctr` | ✅ CTR 6 dimensões + fatigue | `admin.controller.ts` |
| `GET /admin/telegram-groups/quality` | ✅ Quality assessment com signals | `admin.controller.ts` |
| `GET /admin/growth` | ✅ Pipeline health dashboard executivo | `admin.controller.ts` |

### Trilha B — Crypto Research

| Componente | Status | Arquivo |
|---|---|---|
| `ResearchOrchestrator` | ✅ Pipeline sweep+cenários+ranking+QA+portfólio com lineage | `research/research_orchestrator.py` |
| `StrategyIntelligenceAnalyzer` | ✅ Degradação/overfit/fragilidade/regime; consistency score | `research/strategy_intelligence.py` |
| `PortfolioIntelligence` | ✅ Vol targeting, exposure balance, correlação, regime-aware | `research/portfolio_intelligence.py` |
| `DatasetIntelligence` | ✅ Exchange/pair reliability ranking, drift persistence | `analytics/dataset_intelligence.py` |
| `ScenarioIntelligence` | ✅ Stress score, chained scenarios, stress report | `research/scenario_intelligence.py` |
| `crypto_quant_executive.json` | ✅ Dashboard Grafana — 5 rows: strategies/degradation/portfolio/scenarios/dataset | `grafana/dashboards/crypto_quant_executive.json` |
| 8 novas métricas Prometheus | ✅ orchestration_runs, degradation_total, rebalance_total, drift_score, replay_stress, scenario_stress, consistency_score, correlation_avg | `api/metrics.py` |

## Adicionado em Phase K

### Trilha A — Poupi Baby

| Componente | Status | Arquivo |
|---|---|---|
| SocialPayloadBuilder | ✅ Schema v1.0 — savings, categoryEmoji, messageTextHtml, messageSummary | `telegram-groups/social-payload.builder.ts` |
| DistributionChannel interface | ✅ Contrato limpo para n8n/Gemini/Instagram/Threads | `telegram-groups/distribution-channel.interface.ts` |
| TelegramGroupAnalyticsService | ✅ byCategory, byDealTier, byDay, topGroups, approvalFunnel | `telegram-groups/telegram-group-analytics.service.ts` |
| GET /admin/telegram-groups/analytics | ✅ Endpoint com 5 dimensões de análise | `admin/admin.controller.ts` |
| Editorial QA | ✅ savings line, category emoji, CTA melhorado, trust signal | `telegram-group.processor.ts` |
| distribution_thresholds.md | ✅ Thresholds operacionais documentados | `ai/contexts/distribution_thresholds.md` |

### Trilha B — Crypto Research

| Componente | Status | Arquivo |
|---|---|---|
| scenario_runner.py | ✅ 6 cenários nomeados (bull, bear, sideways, high_vol, news_shock, post_halving) | `research/scenario_runner.py` |
| portfolio_simulator.py | ✅ Multi-estratégia ponderada, correlation, diversification_ratio | `research/portfolio_simulator.py` |
| ExperimentTracker tags/lineage | ✅ tags, group_id, parent_run_id — filtragem por tag e grupo | `research/experiment_tracker.py` |
| StrategyRanker head-to-head | ✅ compare_head_to_head() + Prometheus score update | `research/strategy_ranker.py` |
| dataset_qa fleet metrics | ✅ dataset_qa_fleet_score + dataset_qa_critical_count wired | `analytics/dataset_qa.py` |
| sweep_runner Prometheus | ✅ sweep_runs_total + sweep_combinations_tested_total wired | `research/sweep_runner.py` |
| crypto_research.json (Grafana) | ✅ 14 painéis: backtest, sweep, scores, OHLCV, portfolio | `grafana/dashboards/crypto_research.json` |
| 8 novas métricas Prometheus | ✅ sweep_runs, combinations, experiment_records, composite_score, scenarios, portfolio, fleet | `api/metrics.py` |

## Adicionado em Phase I

### Trilha A — Poupi Baby

| Componente | Status | Arquivo |
|---|---|---|
| TelegramGroup model (Prisma) | ✅ Implementado | `prisma/schema.prisma` |
| TelegramGroupPost model (Prisma) | ✅ Implementado | `prisma/schema.prisma` |
| TELEGRAM_GROUP_QUEUE + TelegramGroupJobData | ✅ | `shared/queues/queue.constants.ts` |
| TelegramGroupRateLimiter | ✅ daily counter + interval cooldown | `telegram-groups/telegram-group-rate-limiter.service.ts` |
| CacheService.increment() | ✅ Redis INCR atômico | `cache/cache.service.ts` |
| TelegramGroupsService | ✅ CRUD + selectEligibleGroups + recordPost | `telegram-groups/telegram-groups.service.ts` |
| TelegramGroupPublisher | ✅ enfileira sem I/O de rede | `telegram-groups/telegram-group-publisher.service.ts` |
| TelegramGroupProcessor | ✅ BullMQ worker com double-check | `telegram-groups/telegram-group.processor.ts` |
| TelegramGroupsModule | ✅ registrado em app.module.ts | `telegram-groups/telegram-groups.module.ts` |
| tgGroupPostsTotal counter | ✅ poupi_tg_group_posts_total{group_name, status} | `metrics/metrics.service.ts` |
| Grafana +5 painéis (total: 19) | ✅ | `grafana/provisioning/dashboards/poupi_baby.json` |

### Trilha B — Crypto Research QA

| Componente | Status | Arquivo |
|---|---|---|
| ExperimentQA | ✅ 7 categorias de validação, quality_score 0-100 | `research/experiment_qa.py` |
| StrategyRanker | ✅ Score composto 6 componentes, CLI | `research/strategy_ranker.py` |
| DatasetQA | ✅ Fleet-wide OHLCV, 4 classes qualidade, CLI | `analytics/dataset_qa.py` |

## Gaps Prioritários Remanescentes

- **I-I-01 (Alta)**: Seed de grupos Telegram reais (script + execução)
- **I-I-02 (Alta)**: TelegramGroupPublisher não tem trigger automático ainda (publisher existe mas não é chamado)
- **I-I-03 (Média)**: Endpoint admin para criar/listar grupos (`GET/POST /admin/telegram-groups`)
- **I-I-04 (Média)**: DealScoreService não chama publisher automaticamente após score alto
- **H-H-02 (Alta)**: Embutir tracking token nos templates de email (persiste)
- **H-H-07 (Média)**: Integrar BehaviorTrackingService nos controllers (persiste)
- **H-H-10 (Média)**: Prometheus multi-process gap — Pushgateway para worker metrics

## Evolução de Maturidade (Phase H)

| Domínio | Phase G | Phase H |
|---|---|---|
| poupi-baby comportamento | L0 | **L2** |
| Crypto Research Layer | L1 | **L3** |
| OHLCV integrity | L2 | **L3** (Prometheus wired) |
| Backtest observabilidade | L1 | **L3** (metrics wired) |
| Grafana provisioning | L0 | **L2** |
