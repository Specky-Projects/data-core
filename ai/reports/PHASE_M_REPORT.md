# Phase M Report — Adaptive Intelligence Layer

> Gerado: 2026-05-16
> Status: **COMPLETO**

---

## Objetivo

Elevar a plataforma de L5 → Adaptive Intelligence com:
- **Track A (Poupi Baby):** Behavior & Content Intelligence Layer — preferências, distribuição adaptativa, oportunidades inteligentes, feedback loop, recomendações, qualidade comportamental, inteligência de conteúdo
- **Track B (Crypto):** Adaptive Quant Intelligence Layer — degradação quantificada, fragilidade/overfitting, regime-aware, alocação adaptativa (paper), research loop contínuo, recomendações quant, portfólio adaptativo

---

## Arquivos Criados / Modificados

### Track A — Poupi Baby

#### analytics/ (novos)

| Arquivo | Mudança |
|---|---|
| `preference-learning.service.ts` | **NOVO** — preference_score, affinity_score, engagement_score, fatigue_score por usuário e frota |
| `feedback-loop.service.ts` | **NOVO** — post→engajamento→learning loop com insights adaptativos |
| `recommendation.service.ts` | **NOVO** — IntelligenceSummary com recomendações priorizadas (critical→low) |
| `behavior-quality.service.ts` | **NOVO** — behavior_health_score, engagement_decay, distribution_stability |
| `content-intelligence.service.ts` | **NOVO** — title_length, savings_impact, deal_tier_distribution, content_quality |
| `analytics.module.ts` | +5 novos serviços: Preference, Feedback, BehaviorQuality, ContentIntelligence (Recommendation em AdminModule) |

#### telegram-groups/ (novos)

| Arquivo | Mudança |
|---|---|
| `adaptive-distribution.service.ts` | **NOVO** — timing_score, category_relevance, marketplace_relevance, posting_readiness |
| `telegram-groups.module.ts` | +AdaptiveDistributionService |

#### deal-score/ (novos)

| Arquivo | Mudança |
|---|---|
| `opportunity-intelligence.service.ts` | **NOVO** — opportunity_quality_score, expected_ctr_score, behavioral_fit_score |

#### admin/

| Arquivo | Mudança |
|---|---|
| `admin.module.ts` | +RecommendationService, +OpportunityIntelligenceService |
| `admin.controller.ts` | +6 endpoints: /intelligence/{recommendations,posting-readiness,behavior-quality,content,feedback,timing} |

#### metrics/

| Arquivo | Mudança |
|---|---|
| `metrics.service.ts` | +7 métricas Phase M |

---

### Track B — data-core

#### domains/crypto_coin/research/ (novos)

| Arquivo | Mudança |
|---|---|
| `strategy_degradation_intelligence.py` | **NOVO** — degradation_score, health_score, stability_score, robustness_score + Prometheus |
| `fragility_intelligence.py` | **NOVO** — fragility_score, overfitting_score, replay_consistency, perturbation_sensitivity |
| `regime_aware_intelligence.py` | **NOVO** — regime_confidence_score, compatibility_matrix, adaptive_regime_ranking |
| `adaptive_quant_intelligence.py` | **NOVO** — AdaptiveAllocationEngine (paper), QuantRecommendations, AdaptivePortfolio, research_loop |

#### api/

| Arquivo | Mudança |
|---|---|
| `metrics.py` | +6 métricas Phase M (strategy_degradation_score, health, fragility, overfitting, portfolio_health, research_loop_runs) |

#### ai/

| Arquivo | Mudança |
|---|---|
| `ai/contexts/research_behavior_status.md` | +Phase M section (Track A + Track B) |
| `ai/contexts/evolution_status.md` | Distribuição Telegram L4→L5, Crypto Research L5→L5+ |
| `ai/reports/PHASE_M_REPORT.md` | Este arquivo |

---

## Novas Métricas Prometheus

### Poupi Baby (7 métricas)

| Métrica | Tipo | Labels | Descrição |
|---|---|---|---|
| `poupi_adaptive_posting_score` | Gauge | — | Prontidão adaptativa 0–100 |
| `poupi_timing_score` | Gauge | — | Score de timing baseado em histórico |
| `poupi_behavior_health_score` | Gauge | — | Saúde comportamental da audiência |
| `poupi_engagement_decay_score` | Gauge | — | Decaimento de engajamento (0=crescendo) |
| `poupi_distribution_stability_score` | Gauge | — | Estabilidade do pipeline de distribuição |
| `poupi_content_quality_score` | Gauge | — | Qualidade do conteúdo distribuído |
| `poupi_feedback_loop_runs_total` | Counter | status | Iterações do feedback loop |

### Crypto / data-core (6 métricas)

| Métrica | Tipo | Labels | Descrição |
|---|---|---|---|
| `strategy_degradation_score` | Gauge | strategy_id | Score quantitativo de degradação |
| `strategy_health_score` | Gauge | strategy_id | Saúde da estratégia (0–100) |
| `strategy_fragility_score` | Gauge | strategy_id | Fragilidade de parâmetros |
| `strategy_overfitting_score` | Gauge | strategy_id | Risco de overfitting |
| `portfolio_health_score` | Gauge | — | Saúde adaptativa do portfólio |
| `research_loop_runs_total` | Counter | status | Iterações do research loop |

---

## API Endpoints (Track A)

| Endpoint | Descrição |
|---|---|
| `GET /admin/intelligence/recommendations` | Sumário de inteligência + recomendações priorizadas + intelligenceScore |
| `GET /admin/intelligence/posting-readiness` | Prontidão adaptativa para postar agora (score + timing + diversity) |
| `GET /admin/intelligence/behavior-quality` | Saúde comportamental da audiência (decay + stability) |
| `GET /admin/intelligence/content?days=30` | Padrões de conteúdo (título, savings, deal tier) |
| `GET /admin/intelligence/feedback?days=30` | Ciclo de feedback + health do loop |
| `GET /admin/intelligence/timing` | Score de timing do horário atual |

---

## CLI Commands (Track B)

```bash
# Strategy Degradation Intelligence
python -m domains.crypto_coin.research.strategy_degradation_intelligence --strategy trend_following
python -m domains.crypto_coin.research.strategy_degradation_intelligence --all --rank

# Fragility & Overfitting Intelligence
python -m domains.crypto_coin.research.fragility_intelligence --strategy trend_following
python -m domains.crypto_coin.research.fragility_intelligence --all --json

# Regime-Aware Intelligence
python -m domains.crypto_coin.research.regime_aware_intelligence --strategies trend_following breakout
python -m domains.crypto_coin.research.regime_aware_intelligence --current-regime bull_market --strategies trend_following

# Adaptive Allocation (paper only)
python -m domains.crypto_coin.research.adaptive_quant_intelligence --allocation --strategies trend_following breakout

# Quant Recommendations
python -m domains.crypto_coin.research.adaptive_quant_intelligence --recommendations --strategies trend_following

# Portfolio Health
python -m domains.crypto_coin.research.adaptive_quant_intelligence --portfolio-health --strategies trend_following breakout

# Continuous Research Loop
python -m domains.crypto_coin.research.adaptive_quant_intelligence --research-loop --strategies trend_following breakout
```

---

## Scores Produzidos (Track A)

| Score | Faixa | Origem |
|---|---|---|
| `preference_score` | 0–100 | PreferenceLearningService — afinidade usuário×categoria |
| `affinity_score` | 0–100 | PreferenceLearningService — afinidade usuário×marketplace |
| `engagement_score` | 0–100 | PreferenceLearningService — nível de engajamento |
| `fatigue_score` | 0–100 | PreferenceLearningService — fadiga (dismissals) |
| `adaptive_posting_score` | 0–100 | AdaptiveDistributionService — prontidão composta |
| `timing_score` | 0–100 | AdaptiveDistributionService — horário atual vs. histórico |
| `category_relevance_score` | 0–100 | AdaptiveDistributionService — relevância da categoria no mix |
| `opportunity_quality_score` | 0–100 | OpportunityIntelligenceService — DealScore + boost comportamental (+0 a +15) |
| `expected_ctr_score` | 0–100 | OpportunityIntelligenceService — CTR esperado por cat/marketplace |
| `behavioral_fit_score` | 0–100 | OpportunityIntelligenceService — fit entre oferta e audiência |
| `behavior_health_score` | 0–100 | BehaviorQualityService — saúde geral do comportamento |
| `engagement_decay_score` | 0–100 | BehaviorQualityService — decaimento de engajamento |
| `distribution_stability_score` | 0–100 | BehaviorQualityService — estabilidade do volume diário |
| `content_quality_score` | 0–100 | ContentIntelligenceService — qualidade do mix de conteúdo |
| `intelligence_score` | 0–100 | RecommendationService — saúde geral da inteligência |

## Scores Produzidos (Track B)

| Score | Faixa | Origem |
|---|---|---|
| `degradation_score` | 0–100 | StrategyDegradationIntelligence |
| `strategy_health_score` | 0–100 | StrategyDegradationIntelligence |
| `stability_score` | 0–100 | StrategyDegradationIntelligence |
| `robustness_score` | 0–100 | StrategyDegradationIntelligence |
| `composite_risk_score` | 0–100 | StrategyDegradationIntelligence |
| `fragility_score` | 0–100 | FragilityIntelligenceAnalyzer |
| `overfitting_score` | 0–100 | FragilityIntelligenceAnalyzer |
| `replay_consistency_score` | 0–100 | FragilityIntelligenceAnalyzer |
| `perturbation_sensitivity` | 0–100 | FragilityIntelligenceAnalyzer |
| `regime_confidence_score` | 0–100 | RegimeAwareIntelligence |
| `portfolio_health_score` | 0–100 | AdaptivePortfolioIntelligence |
| `diversification_quality_score` | 0–100 | AdaptivePortfolioIntelligence |
| `adaptive_portfolio_score` | 0–100 | AdaptivePortfolioIntelligence |

---

## Maturidade

| Domínio | Phase L | Phase M |
|---|---|---|
| Poupi Baby — Distribuição | L4 | **L5** |
| Crypto Research Layer | L5 | **L5+** (adaptive quant intelligence) |

**L5 (Poupi Baby)**: Pipeline orquestrada + inteligência adaptativa de preferências + feedback loop + recomendações operacionais + 21 métricas Prometheus total.

**L5+ (Crypto)**: Tudo do L5 + scores quantitativos de degradação/fragilidade/regime + alocação adaptativa (paper) + research loop contínuo + recomendações quant.

---

## Restrições Mantidas

- ✅ Sem RL (Reinforcement Learning)
- ✅ Sem LLM para predição ou geração de trades
- ✅ Sem crypto público (apenas análise de pesquisa interna)
- ✅ Adaptive allocation é PAPER ONLY — requer aprovação humana
- ✅ Sem spam de distribuição — todos os safety rails da Phase L mantidos
- ✅ Sem crescimento agressivo — crescimento orgânico baseado em qualidade

---

## Gaps Pendentes (Phase N)

| Gap | Prioridade |
|---|---|
| Click tracking real para Telegram (inline buttons + callback) | P2 |
| Integrar BehaviorTrackingService nos controllers (H-H-07) | P2 |
| Endpoint admin para AlertQualityService (H-H-03) | P2 |
| Tracking token nos templates de email (H-H-02) | P2 |
| Emitir adaptive_posting_score automaticamente via cron | P3 |
| Grafana dashboard Phase M (Poupi Baby + Crypto) | P3 |
| Prometheus multi-process Pushgateway (worker metrics) | P3 |
| Research loop cron semanal automático | P3 |
