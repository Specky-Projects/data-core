# BUSINESS OS 1.4 — CONNECTOR FRAMEWORK

**Version:** knowledge-connectors-v1-1.4  
**Date:** 2026-06-29  
**Status:** FRAMEWORK COMPLETE — 4 Priority-1 Sources

---

## Universal Connector Contract

All connectors implement `AbstractKnowledgeConnector` (ABC):

```python
class AbstractKnowledgeConnector(ABC):
    connector_name: str
    source_type: SourceType

    def ingest(evaluation_context) -> list[KnowledgeItem]  # FINAL
    def fetch(evaluation_context) -> ConnectorResult        # ABSTRACT
    def normalize(raw) -> NormalizedItem                    # ABSTRACT
    def extract_entities(item) -> list[EntityCandidate]    # ABSTRACT
    def extract_evidence(item, source) -> list[KnowledgeEvidence]  # ABSTRACT
    def generate_metadata(item) -> dict                    # ABSTRACT
```

The `ingest()` method is **final** — it orchestrates all steps and cannot be overridden. Source-specific logic lives exclusively in `fetch/normalize/extract_entities/extract_evidence/generate_metadata`.

---

## Priority-1 Sources

| Connector | Source Type | Auth | Override |
|---|---|---|---|
| `GitHubConnector` | GITHUB | None (public API) | `_raw_override` |
| `HackerNewsConnector` | HACKER_NEWS | None (Firebase API) | `_raw_override` |
| `RSSConnector` | RSS | None | `_raw_override` |
| `BlogConnector` | BLOG | None | `_raw_override` |

All connectors accept `_raw_override: list[dict] | None` for test injection. When set, no HTTP calls are made.

---

## Testability

Every connector is independently testable without network access via `_raw_override`. The test suite injects synthetic raw payloads and validates the full pipeline through to `KnowledgeItem` output.

---

## Extension Pattern

To add a new source (Priority 2+):

1. Create `app/knowledge/connectors/<source>.py`
2. Subclass `AbstractKnowledgeConnector`
3. Implement all 5 abstract methods
4. Add `_raw_override` parameter to constructor
5. Add tests to `test_knowledge_stage_1_4.py`
6. Register in orchestrator/api as needed
