"""Append-only evidence registry for Poupi Baby opportunity emissions."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def default_registry_path() -> Path:
    configured = os.getenv("POUPI_BABY_OPPORTUNITY_REGISTRY_PATH")
    if configured:
        return Path(configured)
    return Path("runtime_data") / "poupi_baby_opportunity_registry.jsonl"


class JsonlOpportunityEvidenceRegistry:
    """Small append-only registry used by the bridge until DB wiring is explicit."""

    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path) if path is not None else default_registry_path()

    def append(self, record: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=True, sort_keys=True))
            fh.write("\n")

    def list_recent(self, limit: int = 50) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        lines = self.path.read_text(encoding="utf-8").splitlines()
        rows: list[dict[str, Any]] = []
        for line in lines[-max(limit, 0):]:
            if line.strip():
                rows.append(json.loads(line))
        return rows

    def latest(self) -> dict[str, Any] | None:
        rows = self.list_recent(1)
        return rows[0] if rows else None
