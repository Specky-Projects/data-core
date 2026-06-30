"""ResearchCache — caches research results by stable_hash of inputs."""
from __future__ import annotations

from app.research_engine.contracts import ResearchResult
from app.scientific_identity.contract import stable_hash


class ResearchCache:
    def __init__(self) -> None:
        self._store: dict[str, ResearchResult] = {}

    def _key(self, kind: str, inputs: dict) -> str:
        return stable_hash({"kind": kind, "inputs": inputs})

    def get(self, kind: str, inputs: dict) -> ResearchResult | None:
        return self._store.get(self._key(kind, inputs))

    def set(self, kind: str, inputs: dict, result: ResearchResult) -> None:
        self._store[self._key(kind, inputs)] = result

    def size(self) -> int:
        return len(self._store)
