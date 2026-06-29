# BUSINESS OS 1.4 — ENTITY RESOLUTION REPORT

**Version:** entity-resolution-v1-1.4  
**Date:** 2026-06-29  
**Status:** COMPLETE

---

## Algorithm

Entity resolution uses **deterministic identity** based on normalized name + type:

```python
entity_id = _k_stable_hash({"name": normalize(canonical_name), "type": entity_type})
```

Resolution pipeline:
1. Normalize raw name: lowercase, strip punctuation, sort tokens
2. Apply alias map: resolve known aliases to canonical names
3. Build deterministic `entity_id`
4. Merge duplicates: max confidence, accumulated mention count

---

## Alias Map (selected entries)

| Raw Input | Canonical |
|---|---|
| OpenAI Inc. / open ai / inc openai | openai |
| Facebook / Meta Platforms | meta |
| Amazon Web Services / amazon services web | aws |
| Microsoft Corporation | microsoft |
| k8s | kubernetes |
| LLM / large language models | large language model |
| ML | machine learning |

---

## Cross-Connector Merge

`merge_entity_lists(lists)` merges entity lists from multiple connectors:
- Same `entity_id` → merge (max confidence, combined evidence, sources_count++)
- Different `entity_id` → keep separate
- Output sorted by: confidence (desc), canonical_name (asc)

---

## Validation Results (test suite)

| Test | Result |
|---|---|
| Alias resolution: OpenAI Inc. → openai | PASS |
| Alias resolution: Amazon Web Services → aws | PASS |
| Alias resolution: k8s → kubernetes | PASS |
| Deduplication across 2 candidates | PASS |
| Confidence max merge | PASS |
| Different types stay separate | PASS |
| Cross-connector merge | PASS |
| entity_id deterministic across case | PASS |
