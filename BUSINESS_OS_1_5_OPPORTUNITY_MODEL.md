# BUSINESS OS 1.5 — OPPORTUNITY MODEL

**Version:** business-os-1.5-opportunity  
**Date:** 2026-06-29  
**Status:** COMPLETE

---

## Core DTO: `Opportunity`

The canonical Opportunity is the primary output of the Opportunity layer.

| Field | Type | Description |
|---|---|---|
| `opportunity_id` | `str` | Deterministic ID from title + domain + type |
| `title` | `str` | Human-readable name |
| `summary` | `str` | One-line synthesis |
| `description` | `str` | Full detail |
| `confidence` | `float [0,1]` | Evidence-derived confidence |
| `priority` | `float [0,1]` | Composite score-driven priority |
| `novelty` | `float [0,1]` | How new relative to known baseline |
| `maturity` | `float [0,1]` | How established the opportunity is |
| `urgency` | `float [0,1]` | Time pressure signal |
| `impact` | `float [0,1]` | Estimated impact magnitude |
| `opportunity_type` | `OpportunityType` | TECHNOLOGY / MARKET / RESEARCH / … |
| `market` | `str` | Target market (optional) |
| `domain` | `str` | Domain (technology, research, …) |
| `evidence` | `list[KnowledgeEvidence]` | Supporting evidence fragments |
| `entities` | `list[KnowledgeEntity]` | Participating entities |
| `relationships` | `list[KnowledgeRelationship]` | Graph relationships |
| `sources` | `list[KnowledgeSource]` | Source descriptors |
| `correlations` | `list[KnowledgeCorrelation]` | Cross-source correlations |
| `provenance` | `OpportunityProvenance` | Full lineage |
| `score` | `OpportunityScore` | 10-dimension score |
| `explanation` | `OpportunityExplanation` | Why it exists + all rationales |
| `lifecycle_stage` | `LifecycleStage` | NEW / EARLY / GROWING / MATURE / DECLINING / ARCHIVED |
| `evolution_history` | `list[OpportunityEvolutionSnapshot]` | Historical snapshots |
| `versions` | `OpportunityVersionMetadata` | Full version lineage |
| `created_at` / `updated_at` | `datetime` | Anchored to EvaluationContext |

---

## Supporting DTOs

| DTO | Purpose |
|---|---|
| `OpportunityScore` | 10-dimension evidence-derived score |
| `OpportunityProvenance` | Knowledge lineage (items, correlations, entities) |
| `OpportunityExplanation` | Why it exists + ranking/lifecycle/confidence rationales |
| `OpportunityEvolutionSnapshot` | Point-in-time metric snapshot |
| `OpportunityHealth` | 10-dimension Opportunity layer health |
| `PortfolioNode` | Hierarchical portfolio grouping node |
| `OpportunityReport` | Top-level pipeline output |
| `OpportunityVersionMetadata` | All version constants in one place |

---

## Version Constants

```python
OPPORTUNITY_VERSION     = "business-os-1.5-opportunity"
DISCOVERY_VERSION       = "opportunity-discovery-v1-1.5"
SCORING_VERSION         = "opportunity-scoring-v1-1.5"
RANKING_VERSION         = "opportunity-ranking-v1-1.5"
LIFECYCLE_VERSION       = "opportunity-lifecycle-v1-1.5"
PORTFOLIO_VERSION       = "opportunity-portfolio-v1-1.5"
HEALTH_VERSION          = "opportunity-health-v1-1.5"
EXPLAINABILITY_VERSION  = "opportunity-explainability-v1-1.5"
EVOLUTION_VERSION       = "opportunity-evolution-v1-1.5"
```

All 9 constants are distinct. `OpportunityVersionMetadata` also carries `knowledge_version` from 1.4, preserving cross-layer traceability.

---

## Determinism Guarantees

- `opportunity_id = _k_stable_hash({"title": ..., "domain": ..., "type": ...})`
- `provenance.provenance_hash` computed in `model_post_init` from content, not wall-clock
- `OpportunityEvolutionSnapshot.snapshot_id = _k_stable_hash({"opp": ..., "ts": ts.isoformat()})`
- All timestamps anchored to `EvaluationContext.evaluation_timestamp`
