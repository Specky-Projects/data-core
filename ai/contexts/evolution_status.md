# Evolution Status — Poupi Platform

> Last updated: 2026-05-17 (Phase S — Runtime Burn-In, Observability Validation & Data Reliability)
> Full detail: `docs/EVOLUTION_MATRIX.md`

## Maturidade Atual por Domínio

| Domínio | Nível | Notas |
|---|---|---|
| Crypto OHLCV pipeline | `L3` | DB replay offline, Prometheus completo (F-03+G-12) |
| Crypto Research Layer | `L9 Estabilizado` | burn-in ativo + observability validation + collector reliability (Phase S) |
| TradingBot v4 | `L3` | Sortino/Calmar adicionados (G-08), simulation.py completo |
| Ecommerce pipeline | `L2` | Dados reais, analytics, observabilidade |
| poupi-baby alertas | `L2` | CTR tracking wired (G-03/G-04/G-05), alertsDispatched completo |
| poupi-baby watchlist | `L2` | watchlistActions counter (G-02) |
| poupi-baby oportunidades | `L2` | /deal-score/opportunities (G-06/G-07) |
| poupi-baby distribuição Telegram | `L5` | Auto distribution + adaptive intelligence + feedback loop + recommendations (Phase M) |
| Real Estate pipeline | `L1` | Funcional mas analytics parcial |
| Sports Odds | `L0` | Desativado |

## Implementações Phase S

### Trilha B — Crypto (Runtime Burn-In, Observability Validation & Data Reliability — L9 Stabilization)

- **S-1**: `RuntimeBurninEngine` — 8 dimensões de burn-in via JSONL; fases WARMING_UP/STABILIZING/BURN_IN/MATURE (<4h/4-24h/24-72h/>72h); burnin_stability_score, runtime_burnin_score, long_session_integrity_score; data/runtime_burnin_log.jsonl
- **S-2**: `MetricsIntegrityValidator` — valida freshness de 20 métricas Prometheus via mtime JSONL; limiares 60min (operacional) / 120min (research); metrics_integrity_score, metrics_continuity_score, observability_health_score; data/metrics_integrity_log.jsonl
- **S-3**: `GrafanaDashboardValidator` — valida estrutura de dashboards Grafana localmente (sem conexão); checa title/gridPos/datasource/expr/thresholds por painel; dashboard_integrity_score, panel_health_score, visualization_consistency_score; data/dashboard_validation_log.jsonl
- **S-4**: `CollectorReliabilityEngine` — escaneia data/*.jsonl em buckets fresh(<1h)/recent(1-6h)/stale(6-24h)/dead(>24h); parse health por linha; collector_reliability_score, normalization_integrity_score, data_freshness_score; data/collector_reliability_log.jsonl
- **S-5**: `ReplayIntegrityBurninValidator` — audita 8 sessões JSONL por gaps >30min, parse errors, completeness ratio; status healthy/degraded/corrupt/missing; replay_burnin_score, replay_continuity_score, replay_consistency_score; data/replay_burnin_log.jsonl
- **S-6**: `IncidentNoiseReductionEngine` — detecta storms(>5/30min), duplicates(cooldown violation), cascading(≥3 subsystems), cooldown violations; incident_signal_quality_score, alert_precision_score, operational_noise_score; data/incident_noise_log.jsonl
- **S-7**: `ColdStartResilienceValidator` — 10 checks estruturais sem restart real; Grade A-F; pesos por criticidade (state/config/data=2.0, imports=1.0); cold_start_resilience_score; data/cold_start_validation_log.jsonl
- **S-8**: `OperationalDriftAnalyzer` — stddev 7 dimensões das últimas 10 entradas JSONL; stable(stddev<3)/drifting(3-10)/degrading(>10); operational_drift_score, runtime_consistency_trend, stability_trend_score; data/operational_drift_log.jsonl
- **S-9**: `AutonomousRuntimeStabilityOrchestrator` — orquestra S-1..S-8; runtime_stability_score, observability_readiness_score, burnin_readiness_score, burnin_operational_maturity_score; data/runtime_stability_log.jsonl + data/runtime_stability_summary.jsonl
- **S-10**: `api/burnin_metrics.py` — 33 métricas Prometheus Phase S (29 Gauges + 4 Counters); `burnin_operational_maturity_score` com prefixo burnin_ para evitar colisão com Phase R
- **Dashboard**: `grafana/dashboards/crypto_runtime_burnin.json` — uid=crypto-runtime-burnin-s, 10 seções, 34 painéis; refresh 30s, janela 12h
- **Bridge**: `api/live_metrics_updater.py` → adicionado `refresh_burnin_metrics()` + chamada em `refresh_live_metrics()`
- **Docs**: `ai/docs/runtime_burnin_architecture.md`, `ai/docs/observability_validation_flow.md`, `ai/docs/replay_burnin_validation.md`, `ai/docs/collector_reliability_flow.md`

### S-GAPs conhecidos (próxima fase)
- S-GAP-1: JWT com validação real (autenticação API)
- S-GAP-2: Alertas Grafana via webhook externo
- S-GAP-3: Testes de carga / simulação de volume real
- S-GAP-4: burnin_operational_maturity_score deve atingir ≥80 por ≥72h antes de paper trading validado

## Implementações Phase R

### Trilha B — Crypto (Autonomous Runtime Governance & Production Hardening — L8+ → L9)

- **R-1**: `AutonomousStartupManager` — boot orchestration com 12 checks; startup_health_score, startup_integrity_score, startup_recovery_state (COLD_START/WARM_RESTORE/PARTIAL_RESTORE/FAILED); valida env, DB, Redis, exchange, Prometheus, Grafana, replay storage; persiste data/runtime_state.json
- **R-2**: `OperationalStateRestorationEngine` — persistência e restauração determinística de todo o estado operacional; restoration_integrity_score, state_consistency_score, replay_recovery_score; detecta 7 tipos de inconsistência; data/operational_state.json schema v1.0
- **R-3**: `AutonomousServiceWatchdog` — monitoramento de 10 serviços via file-age + env + import probing; detecta stalled_loop, scheduler_drift, queue_buildup, memory_pressure; watchdog_health_score, loop_integrity_score, runtime_anomaly_score; ações: NONE/MONITOR/FREEZE/ESCALATE/RESTART
- **R-4**: `LongRunningStabilityEngine` — 7 dimensões de estabilidade; runtime_health_score, operational_decay_score, long_running_stability_score, runtime_consistency_score; overall_trend (stable/improving/degrading); status STABLE/DRIFTING/DEGRADING/CRITICAL
- **R-5**: `DeploymentSafetyValidator` — 20 checks em 6 categorias (imports/configs/replay/metrics/governance/compatibility); deployment_safety_score, migration_integrity_score, rollback_risk_score, compatibility_score; bloqueia deploy se ALLOW_LIVE_AUTO_ACTIVATION=true
- **R-6**: `AutonomousIncidentManager` — 5 severidades (INFO→EMERGENCY); TTL automático; data/incident_log.jsonl + data/active_incidents.json; incident_severity_score, incident_frequency_score, operational_risk_score; CLIs: --summary/--create/--resolve/--auto-resolve
- **R-7**: `OperationalRecoveryEngine` — 8 ações de recovery; 5 pre-checks + 5 post-checks obrigatórios; recovery_success_rate, recovery_integrity_score, recovery_duration_ms; pre-check failure → todos SKIPPED; data/recovery_markers.json
- **R-8**: `AutonomousRuntimeGovernance` — orquestrador Phase R; consolida 8 subsistemas; runtime_governance_score, operational_resilience_score, production_readiness_score; autonomous_runtime_state (HEALTHY/DEGRADED/RECOVERING/FROZEN/CRITICAL); live_execution_allowed sempre False
- **R-9**: `ProductionReadinessClassifier` — 7 classificações (DEVELOPMENT→PRODUCTION_READY); readiness_confidence, operational_maturity_score; blocking_factors + advancement_requirements por nível; classification_history
- **R-10**: `api/runtime_metrics.py` — 31 métricas Prometheus Phase R (28 Gauges + 3 Counters); incident_count_total[severity], restart_events_total[reason], critical_incidents_total
- **Dashboard**: `grafana/dashboards/crypto_runtime_governance.json` — 10 seções, 37 painéis; refresh 30s; janela 6h
- **Docs**: `ai/docs/runtime_governance_architecture.md`, `ai/docs/autonomous_startup_flow.md`, `ai/docs/incident_management_flow.md`, `ai/docs/operational_recovery_flow.md`

## Implementações Phase Q

### Trilha B — Crypto (Micro-Live Execution & Capital-Protected Autonomy)

- **Q-FASE-1**: `MicroLiveExecutionController` — state machine paper/live_micro/frozen/rollback; validate_live_trade(), authorize_execution(), emergency_freeze(), transition_to_paper()
- **Q-FASE-2**: `LiveExecutionAuditor` — ExecutionRecord.build(), record_execution(), audit(window=50); detects slippage_deterioration, fill_inconsistency, latency_spike, exchange_degradation; execution_quality_score
- **Q-FASE-3**: `AutonomousLiveGuardian` — 8 deteccoes; 5 estados (NORMAL→MONITORING→CONTRACTING→FROZEN→ROLLBACK); contraction_multiplier; exchange_instability_score
- **Q-FASE-4**: `PaperVsLiveDivergenceEngine` — divergence_score, live_consistency_score, execution_alignment_score; detects slippage_gap, fill_gap, latency_gap, divergence_escalation, execution_bias
- **Q-FASE-5**: `LiveCapitalPreservationEngine` — hard limits: 1%/trade max, 0.25%/trade, 2% daily DD, 4% weekly DD; approved_size_multiplier; capital_freeze
- **Q-FASE-6**: `LiveReadinessRevalidationEngine` — continuous_live_readiness_score; GREEN/YELLOW/ORANGE/RED thresholds; agrega 6 inputs; RED → rollback_recommended
- **Q-FASE-7**: `AutonomousRollbackEngine` — 7 triggers (severity 1-7); incident report; RecoveryRequirements; post_mortem_reference
- **Q-FASE-8**: `LiveExecutionReplayEngine` — replay deterministico; signal_context, indicator_snapshot, orderbook_context, execution_timeline; replay_fidelity_score; deviation_classification (normal|elevated|anomalous|critical)
- **Q-FASE-9**: `AutonomousLiveGovernance` — orchestrador completo; live_governance_score, operational_confidence, live_stability_score, execution_integrity, capital_safety_score, autonomous_live_approval
- **Q-FASE-10**: `api/live_metrics.py` — 14 novas metricas Prometheus: live_governance_score, execution_quality_score, divergence_score, live_consistency_score, guardian_emergency_level, rollback_events_total, live_drawdown_pct, live_capital_exposure_pct, execution_latency_ms, live_slippage_bps, autonomous_freeze_state, live_readiness_score, exchange_instability_score, contraction_multiplier
- **Q-FASE-11**: Dashboard Grafana `crypto_live_governance.json` — 10 secoes, 18 paineis
- **Docs**: `ai/docs/live_governance_architecture.md`, `ai/docs/micro_live_operational_flow.md`, `ai/docs/rollback_and_recovery.md`

## Implementações Phase P

### Trilha B — Crypto (Autonomous Validation & Micro-Live Readiness)

- **P-FASE-1**: `AutonomousBehaviorAuditor` — audit de runaway, governance loops, allocation instability, exposure drift, healing spam
- **P-FASE-3**: `AutonomousStabilityIntelligence` — autonomy_stability_score, allocation_stability_score, governance_consistency_score
- **P-FASE-4**: `CapitalPreservationValidator` — capital_survival_score, preservation_efficiency_score, drawdown_protection_score; 5 checks formais
- **P-FASE-5**: `CatastrophicSimulationEngine` — 6 cenários extremos (flash_crash, cascading_volatility, liquidity_collapse, prolonged_bear, regime_instability, multi_strategy_degradation)
- **P-FASE-6**: `MicroLiveReadinessEngine` — 8 gates (6 blocking) para aprovação formal de micro-live; live_readiness_score
- **P-FASE-7**: `SafeAutonomousConstraints` — max_capital(80%), max_daily_loss(5%), max_per_strategy(35%), max_corr_exposure(50%), emergency_contraction; lineage UUID por violação
- **P-FASE-8**: `ExecutionSimulationEngine` — Monte Carlo por regime (low_vol/medium_vol/high_vol/crisis); execution_realism_score, fill_quality_score, latency_impact_score
- **P-FASE-9**: `GovernanceDriftIntelligence` — governance_drift_score, adaptation_quality_score, autonomous_balance_score; detecta overreaction/underreaction/delay
- **P-FASE-10**: `AutonomousValidationLoop` — loop completo com 8 fases independentes; validation_health_score; aprovação formal para micro-live
- **P-FASE-11**: 9 novas métricas Prometheus: autonomy_stability_score, capital_survival_score, live_readiness_score, governance_drift_score, execution_realism_score, preservation_efficiency_score, autonomous_validation_cycles_total, catastrophic_scenarios_total, emergency_contractions_total
- **P-FASE-12**: Dashboard Grafana `crypto_autonomous_validation.json` — 7 rows, 15 painéis

## Implementações Phase O

### Trilha B — Crypto (Fully Autonomous Quant Governance)

- **O-FASE-2**: `StrategyActivationEngine` — activation_states (active/throttled/frozen/retired), trust-gated recovery, freeze_count lineage
- **O-FASE-3**: `AutonomousExposureControl` — emergency/survival throttling (×0.15–×0.60), emergency_exposure_score, survival_mode_score, volatility_protection_score
- **O-FASE-4**: `AutonomousPortfolioGovernor` (em adaptive_quant_intelligence.py) — portfolio_survival_score, adaptive_resilience_score, portfolio_stress_score, governance_mode
- **O-FASE-5**: `MarketSurvivalIntelligence` — regime_collapse, volatility_explosion, cascading_degradation, strategy_contagion; market_survival_score, systemic_risk_score
- **O-FASE-6**: `AutonomousResearchEvolution` (em autonomous_research_loop.py) — research plan com scenarios, sweeps, datasets, gaps
- **O-FASE-7**: `SelfHealingIntelligence` — detecta corrupt_jsonl, anomalous_metric, replay_inconsistency, lineage_gap; quarantine mechanism; infrastructure_health_score
- **O-FASE-8**: `AutonomousExecutionIntelligence` — execução consolidada: sizing, exposure, allocation, throttling, capital_preservation; lineage UUID por decisão
- **O-FASE-9**: `AdaptiveRiskIntelligence` — adaptive_risk_score, contagion_risk_score, hidden_fragility_score; detecta cascading, correlated failures, parameter explosion, tail risk
- **O-FASE-10**: `MetaOptimizationIntelligence` — optimization_efficiency_score, computational_priority_score, adaptive_efficiency_score; detecta stagnation/redundancy/convergence
- **O-ORCHESTRATOR**: `AutonomousGovernance` — ciclo completo com 9 fases independentes, governance_health_score, autonomy_confidence_score, system_resilience_score
- **O-FASE-11**: 9 novas métricas Prometheus: market_survival_score, systemic_risk_score, strategy_trust_score, portfolio_survival_score, adaptive_risk_score, self_healing_score, autonomous_execution_total, autonomous_strategy_switch_total, adaptive_efficiency_score
- **O-FASE-12**: Dashboard Grafana `crypto_autonomous_governance.json` — 7 rows, 20 painéis

## Implementações Phase N

### Trilha B — Crypto (Autonomous Adaptive Quant Evolution)

- **N-FASE-2**: `MarketDriftIntelligence` — market_drift_score, edge_decay_score, regime_shift_score, volatility_shift_score
- **N-FASE-3**: `StrategyLifecycleEngine` — lifecycle_state (experimental→candidate→validated→degraded→retired), promotion/retirement/recovery scores
- **N-FASE-4**: `AdaptiveExposureIntelligence` — adaptive_exposure_score, stress_exposure_score, regime_exposure_score; caps por lifecycle state
- **N-FASE-5**: `MetaStrategyIntelligence` — correlation_matrix, hedge_compatibility_score, diversification_synergy_score
- **N-FASE-6**: `ResearchPrioritizer` — research/replay/validation priority scores; fila de tarefas priorizada
- **N-FASE-7**: `ParameterIntelligence` — parameter_stability_score, range_quality_score, adaptive_parameter_priority
- **N-FASE-8**: `AdaptivePortfolioEvolution` — portfolio_resilience_score, adaptive_diversification_score, portfolio_drift_score, rebalance triggers
- **N-FASE-9**: `QuantRecommendationEngineV2` — estende Phase M + drift, lifecycle, conflicting pairs
- **N-FASE-10**: `AutonomousResearchScheduler` — loop semi-autônomo completo com lineage, 8 fases por ciclo
- **N-FASE-11**: 9 novas métricas Prometheus: market_drift_score, edge_decay_score, strategy_retirement_total, strategy_promotions_total, adaptive_exposure_score, research_priority_score, parameter_stability_score, portfolio_resilience_score, autonomous_recommendations_total
- **N-FASE-12**: Dashboard Grafana `crypto_autonomous_quant.json` — 7 rows, 20 painéis

## Implementações Phase G

### Trilha A — Poupi Baby
- **G-01/G-02**: `notificationEngaged` (CTR) e `watchlistActions` em MetricsService
- **G-03/G-04**: `NotificationTrackingService` + Controller — GET /notifications/track
- **G-05**: Registro no NotificationsModule
- **G-06/G-07**: `DealScoreService.getTopOpportunities()` + GET /deal-score/opportunities

### Trilha B — Crypto
- **G-08/G-09**: `sortino_ratio()`, `calmar_ratio()`, `exposure_pct()` em calc.py; `compute_all()` expandido
- **G-10**: `ohlcv_integrity.py` — checker completo com gaps, anomalias, duplicatas, price spikes
- **G-11**: `db_replay.py` — replay offline de normalized_market_candles (sem dependência de Binance)
- **G-12**: 5 novas métricas Prometheus: backtest_runs_total, backtest_duration_seconds, backtest_candles_processed_total, ohlcv_integrity_checks_total, ohlcv_gaps_detected_total

## Gaps Phase R

- **R-GAP-01 (Alta)**: `AutonomousStartupManager` sem integração com processo de startup real do uvicorn — hoje valida via file/env checks
- **R-GAP-02 (Alta)**: `AutonomousServiceWatchdog` sem métricas de uso real de memória/CPU (requer psutil e acesso ao processo)
- **R-GAP-03 (Alta)**: `OperationalRecoveryEngine` usa recovery_markers.json como proxy — sem restart real de serviços Docker
- **R-GAP-04 (Média)**: `AutonomousRuntimeGovernance` não agendado como cron job — executado via CLI apenas
- **R-GAP-05 (Média)**: `DeploymentSafetyValidator` sem verificação real de Alembic migration status
- **R-GAP-06 (Média)**: Alertas Grafana não configurados para runtime_governance_score < 40 (CRITICAL)
- **R-GAP-07 (Baixa)**: `ProductionReadinessClassifier` — threshold PRODUCTION_READY requer uptime > 72h, difícil testar sem ambiente de longa duração

## Gaps Phase Q

- **Q-GAP-01 (Alta)**: `MicroLiveExecutionController` sem integração com exchange real — requer Binance Testnet
- **Q-GAP-02 (Alta)**: `LiveExecutionAuditor` precisa de dados reais — hoje usa dados inseridos via CLI
- **Q-GAP-03 (Alta)**: `AutonomousLiveGovernance` não está wired como scheduled task (cron)
- **Q-GAP-04 (Média)**: `LiveCapitalPreservationEngine` total_capital_usd hardcoded
- **Q-GAP-05 (Média)**: Alertas Grafana não configurados para guardian>=CONTRACTING
- **Q-GAP-06 (Média)**: `PaperVsLiveDivergenceEngine` sem baseline de paper trading real paralelo

## Gaps Prioritários Remanescentes

- **G-H-01 (Alta)**: Zero usuários reais — ação de aquisição necessária
- **G-H-02 (Média)**: Token de tracking não gerado nos templates de email ainda
- **G-H-04 (Média)**: OHLCV integrity não agendado como cron — só CLI
- **G-H-05 (Média)**: backtest_runs_total não wired no runner ainda
- **G-H-10 (Média)**: Prometheus multi-process gap — Pushgateway necessário

## O que está PRONTO para uso interno

### Poupi Baby
- `GET /deal-score/opportunities?limit=20&minScore=60` — top oportunidades de compra
- `GET /notifications/track?token=X&type=opened` — pixel de rastreamento (email)
- `GET /notifications/track?token=X&type=clicked&redirect=URL` — redirect rastreado
- Métricas: `poupi_notification_engaged_total`, `poupi_watchlist_actions_total`

### Crypto
- `python -m domains.crypto_coin.analytics.ohlcv_integrity --symbol BTC/USDT --tf 15m --days 30`
- `python -m domains.crypto_coin.backtesting.db_replay --symbol BTC/USDT --tf 15m --days 90`
- `compute_all()` agora retorna: sharpe, sortino, calmar, max_drawdown, expectancy, profit_factor, win_count, loss_count, total_return_pct
