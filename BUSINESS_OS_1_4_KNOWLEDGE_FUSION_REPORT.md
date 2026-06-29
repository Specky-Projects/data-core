# BUSINESS OS 1.4 — KNOWLEDGE FUSION REPORT

**Version:** knowledge-fusion-v1-1.4  
**Date:** 2026-06-29  
**Status:** COMPLETE

---

## Algorithm: Union-Find with 3 Fusion Strategies

Items from different sources are grouped using union-find. Two items are fusible if:

| Strategy | Condition |
|---|---|
| `URL_CANONICAL` | Same URL after stripping query params and trailing slash |
| `ENTITY_OVERLAP` | Jaccard similarity of entity IDs ≥ threshold (default 0.3) |
| `TOPIC_OVERLAP` | Jaccard similarity of topics ≥ threshold (default 0.3) |

Items from the **same source** are never fused.

---

## Fusion Output

- **Single-source items** → `FusedKnowledgeItem` with `source_count=1`
- **Multi-source groups** → `FusedKnowledgeItem` where primary = highest `engagement_score + confidence`; contributing = all others; merged entities (cross-source dedup), merged evidence (dedup by evidence_id), merged topics (union)

---

## Determinism

- union-find parent assignment is order-independent for same input
- `fusion_id` = `_k_stable_hash({"ids": sorted(item_ids)})`
- `fusion_hash` set in `model_post_init` using sorted contributing IDs + strategy

---

## Validation Results

| Test | Result |
|---|---|
| Empty input returns [] | PASS |
| Single item stays single | PASS |
| URL canonical merge | PASS |
| fusion_hash set on all items | PASS |
| Deterministic fusion_id | PASS |
| versions.knowledge_version on all fused | PASS |
