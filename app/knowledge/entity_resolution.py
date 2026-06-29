"""Universal Entity Resolution — Stage 4.

Detects and merges duplicate entities deterministically.
Identity is based on normalized name + type — no wall-clock dependency.
"""

from __future__ import annotations

from typing import Any

from app.knowledge.dto import (
    EntityCandidate,
    EntityProvenance,
    EntityType,
    KnowledgeEntity,
    KnowledgeEvidence,
    KnowledgeVersionMetadata,
    _normalize_entity_name,
    build_entity_id,
)

_ALIAS_MAP: dict[str, str] = {
    "open ai": "openai",
    "openai inc": "openai",
    "openai inc.": "openai",
    "inc openai": "openai",
    "google llc": "google",
    "alphabet inc": "google",
    "alphabet": "google",
    "meta platforms": "meta",
    "facebook": "meta",
    "amazon web services": "aws",
    "amazon services web": "aws",
    "microsoft corporation": "microsoft",
    "apple inc": "apple",
    "pytorch": "pytorch",
    "tensorflow": "tensorflow",
    "ml": "machine learning",
    "ai": "artificial intelligence",
    "llm": "large language model",
    "large language models": "large language model",
    "k8s": "kubernetes",
    "js": "javascript",
    "ts": "typescript",
    "py": "python",
}


def _canonical_name(raw: str) -> str:
    """Return canonical name: check alias map then normalized form."""
    normalized = _normalize_entity_name(raw)
    return _ALIAS_MAP.get(normalized, normalized)


def resolve_entities(
    candidates: list[EntityCandidate],
    source_id: str,
    evidence: list[KnowledgeEvidence],
) -> list[KnowledgeEntity]:
    """Deterministically resolve candidates into deduplicated KnowledgeEntity list."""
    seen: dict[str, KnowledgeEntity] = {}

    for candidate in candidates:
        canonical = _canonical_name(candidate.raw_name)
        entity_id = build_entity_id(canonical, candidate.entity_type)

        if entity_id in seen:
            existing = seen[entity_id]
            if candidate.raw_name not in existing.aliases:
                existing.aliases.append(candidate.raw_name)
            existing.confidence = max(existing.confidence, candidate.confidence)
            existing.provenance.mention_count += 1
        else:
            evidence_ids = sorted({e.evidence_id for e in evidence})[:10]
            seen[entity_id] = KnowledgeEntity(
                entity_id=entity_id,
                canonical_name=canonical,
                normalized_name=_normalize_entity_name(canonical),
                aliases=[candidate.raw_name] if candidate.raw_name.lower() != canonical else [],
                entity_type=candidate.entity_type,
                confidence=candidate.confidence,
                provenance=EntityProvenance(
                    first_seen_source=source_id,
                    evidence_ids=evidence_ids,
                    mention_count=1,
                    sources_count=1,
                ),
            )

    return list(seen.values())


def merge_entity_lists(lists: list[list[KnowledgeEntity]]) -> list[KnowledgeEntity]:
    """Merge multiple entity lists from different sources into one deduplicated list."""
    merged: dict[str, KnowledgeEntity] = {}

    for entity_list in lists:
        for entity in entity_list:
            if entity.entity_id in merged:
                existing = merged[entity.entity_id]
                for alias in entity.aliases:
                    if alias not in existing.aliases:
                        existing.aliases.append(alias)
                existing.confidence = max(existing.confidence, entity.confidence)
                existing.provenance.mention_count += entity.provenance.mention_count
                existing.provenance.sources_count += 1
                combined_ids = sorted(set(existing.provenance.evidence_ids + entity.provenance.evidence_ids))[:25]
                existing.provenance.evidence_ids = combined_ids
            else:
                merged[entity.entity_id] = entity.model_copy(deep=True)

    return sorted(merged.values(), key=lambda e: (-e.confidence, e.canonical_name))
