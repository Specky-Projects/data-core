# BUSINESS OS 1.4 — CANONICAL KNOWLEDGE MODEL

**Version:** business-os-1.4-knowledge  
**Date:** 2026-06-29  
**Status:** MODEL COMPLETE

---

## Core DTOs

| DTO | Purpose |
|---|---|
| `KnowledgeSource` | Source descriptor with type, URL, name |
| `KnowledgeEvidence` | Atomic evidence fragment from a source |
| `EntityCandidate` | Raw entity candidate before resolution |
| `EntityProvenance` | Where an entity was first seen |
| `KnowledgeEntity` | Resolved canonical entity with aliases |
| `KnowledgeProvenance` | Full lineage of a knowledge item |
| `KnowledgeFreshness` | 4-dimension freshness model |
| `KnowledgeItem` | Canonical knowledge item (primary DTO) |
| `FusedKnowledgeItem` | Multi-source merged knowledge item |
| `KnowledgeRelationship` | Logical edge in the knowledge graph |
| `KnowledgeCorrelation` | Cross-source signal |
| `KnowledgeHealth` | 10-dimension platform health |
| `KnowledgeReport` | Top-level pipeline output |

---

## Version Constants

```python
KNOWLEDGE_VERSION            = "business-os-1.4-knowledge"
CONNECTOR_VERSION            = "knowledge-connectors-v1-1.4"
ENTITY_RESOLUTION_VERSION    = "entity-resolution-v1-1.4"
FUSION_VERSION               = "knowledge-fusion-v1-1.4"
CORRELATION_VERSION          = "cross-source-correlation-v1-1.4"
GRAPH_VERSION                = "knowledge-graph-v1-1.4"
PROVENANCE_VERSION           = "knowledge-provenance-v1-1.4"
```

All DTOs carry `versions: KnowledgeVersionMetadata` for full version lineage on every output.

---

## Utility Functions

| Function | Output |
|---|---|
| `_k_stable_hash(obj)` | SHA-256 hex[:32] of canonical JSON |
| `_normalize_entity_name(name)` | Lowercase, punctuation removed, tokens sorted |
| `build_entity_id(name, type)` | Deterministic entity identity |
| `build_item_id(url, source_id)` | Deterministic item identity |
| `build_evidence_id(src, content, ts)` | Deterministic evidence identity |
| `build_relationship_id(a, b, type)` | Symmetric relationship identity |
| `build_correlation_id(entities, signal, window)` | Deterministic correlation identity |
| `build_knowledge_provenance(...)` | Full provenance construction |
| `compute_knowledge_freshness(...)` | Evidence-anchored freshness |
| `compute_knowledge_health(...)` | 10-dimension health score |

---

## Shadow Contracts (1.5+ interfaces)

`Goal`, `Decision`, `ExecutionPlan`, `ExecutionTask`, `ExecutionResult`, `ExecutionAudit` are defined as Pydantic models with no runtime behavior. They represent the interface contract for future execution layers.
