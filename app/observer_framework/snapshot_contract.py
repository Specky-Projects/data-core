"""RuntimeSnapshotContract — the canonical, deterministic interface between
production (Business OS) and Claude Code.

Reuses the existing ObservationRecord / ObservationSeverity / ObservationHealth
taxonomy from app.observation_engine.contracts (no duplication) and the
canonical stable_hash from app.scientific_identity.contract for integrity.

A snapshot is:
  - deterministic: identical inputs produce an identical integrity_hash
  - self-verifying: verify_integrity() detects tampering or truncation
  - JSON-serialisable: to_dict()/from_dict() round-trip losslessly
  - read-only: nothing in this module writes to production; it only
    describes and validates data that was already collected elsewhere
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

from app.observation_engine.contracts import (
    OBSERVATION_RECORD_VERSION,
    ObservationHealth,
    ObservationRecord,
    ObservationSeverity,
)
from app.scientific_identity.contract import stable_hash

SNAPSHOT_CONTRACT_VERSION = "runtime-snapshot-v1"


# ── Severity/health ranking (reused across diagnosis + certification) ────────

_SEVERITY_RANK = {
    ObservationSeverity.INFO: 0,
    ObservationSeverity.WARNING: 1,
    ObservationSeverity.ERROR: 2,
    ObservationSeverity.CRITICAL: 3,
}
_HEALTH_RANK = {
    ObservationHealth.HEALTHY: 0,
    ObservationHealth.UNKNOWN: 1,
    ObservationHealth.DEGRADED: 2,
    ObservationHealth.CRITICAL: 3,
}


def severity_rank(s: ObservationSeverity) -> int:
    return _SEVERITY_RANK.get(s, 0)


def health_rank(h: ObservationHealth) -> int:
    return _HEALTH_RANK.get(h, 1)


# ── JSON-safe record projection ───────────────────────────────────────────────


@dataclass(frozen=True)
class ObservationRecordSnapshot:
    """JSON-safe, immutable projection of an ObservationRecord."""

    observation_id: str
    scientific_id: str
    lineage_id: str
    project: str
    domain: str
    source: str
    severity: str
    health: str
    evidence: tuple[str, ...]
    metrics: dict[str, float]
    timestamp: str
    advisory_only: bool
    version: str

    @classmethod
    def from_record(cls, record: ObservationRecord) -> ObservationRecordSnapshot:
        return cls(
            observation_id=record.observation_id,
            scientific_id=record.scientific_id,
            lineage_id=record.lineage_id,
            project=record.project,
            domain=record.domain,
            source=record.source,
            severity=record.severity.value,
            health=record.health.value,
            evidence=tuple(record.evidence),
            metrics=dict(record.metrics),
            timestamp=record.timestamp.isoformat() if isinstance(record.timestamp, datetime) else str(record.timestamp),
            advisory_only=record.advisory_only,
            version=record.version,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self) | {"evidence": list(self.evidence)}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ObservationRecordSnapshot:
        return cls(
            observation_id=data["observation_id"],
            scientific_id=data["scientific_id"],
            lineage_id=data["lineage_id"],
            project=data["project"],
            domain=data["domain"],
            source=data["source"],
            severity=data["severity"],
            health=data["health"],
            evidence=tuple(data.get("evidence") or ()),
            metrics=dict(data.get("metrics") or {}),
            timestamp=data["timestamp"],
            advisory_only=bool(data.get("advisory_only", True)),
            version=data.get("version", OBSERVATION_RECORD_VERSION),
        )

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.observation_id.strip():
            errors.append("observation_id must not be empty")
        if not self.source.strip():
            errors.append("source must not be empty")
        if self.severity not in {s.value for s in ObservationSeverity}:
            errors.append(f"unknown severity: {self.severity}")
        if self.health not in {h.value for h in ObservationHealth}:
            errors.append(f"unknown health: {self.health}")
        if not self.advisory_only:
            errors.append("advisory_only must be True")
        return errors


@dataclass(frozen=True)
class AdapterHealthSnapshot:
    adapter: str
    status: str
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AdapterHealthSnapshot:
        return cls(adapter=data["adapter"], status=data["status"], detail=dict(data.get("detail") or {}))

    @classmethod
    def from_raw(cls, data: dict[str, Any]) -> AdapterHealthSnapshot:
        """Tolerant constructor for an adapter's raw health() dict — any key
        besides `adapter`/`status` is folded into `detail` rather than raising."""
        extra = {k: v for k, v in data.items() if k not in ("adapter", "status", "detail")}
        detail = {**dict(data.get("detail") or {}), **extra}
        return cls(adapter=data["adapter"], status=data["status"], detail=detail)


# ── Top-level snapshot envelope ──────────────────────────────────────────────


@dataclass(frozen=True)
class RuntimeSnapshotContract:
    """The sole interface between production and Claude Code.

    ``collector_status`` records which of the expected collectors (per
    COLLECTOR_SPECIFICATION.md) actually contributed a record — a collector
    absent here means "not observed in this snapshot", never "assumed healthy".
    """

    snapshot_id: str
    captured_at: str
    schema_version: str
    source: str
    records: tuple[ObservationRecordSnapshot, ...]
    adapter_health: tuple[AdapterHealthSnapshot, ...]
    integrity_hash: str
    runtime_version: str = "unknown"
    build_revision: str | None = None

    @classmethod
    def create(
        cls,
        *,
        source: str,
        records: list[ObservationRecord] | list[ObservationRecordSnapshot],
        adapter_health: list[dict[str, Any]] | list[AdapterHealthSnapshot],
        captured_at: str | None = None,
        runtime_version: str = "unknown",
        build_revision: str | None = None,
    ) -> RuntimeSnapshotContract:
        captured_at = captured_at or datetime.utcnow().isoformat()
        rec_snapshots = tuple(
            r if isinstance(r, ObservationRecordSnapshot) else ObservationRecordSnapshot.from_record(r)
            for r in records
        )
        health_snapshots = tuple(
            h if isinstance(h, AdapterHealthSnapshot) else AdapterHealthSnapshot.from_raw(h)
            for h in adapter_health
        )
        payload = {
            "source": source,
            "captured_at": captured_at,
            "records": [r.to_dict() for r in rec_snapshots],
            "adapter_health": [h.to_dict() for h in health_snapshots],
            "runtime_version": runtime_version,
            "build_revision": build_revision,
        }
        integrity_hash = stable_hash(payload)
        return cls(
            snapshot_id=stable_hash({"source": source, "captured_at": captured_at, "integrity_hash": integrity_hash}),
            captured_at=captured_at,
            schema_version=SNAPSHOT_CONTRACT_VERSION,
            source=source,
            records=rec_snapshots,
            adapter_health=health_snapshots,
            integrity_hash=integrity_hash,
            runtime_version=runtime_version,
            build_revision=build_revision,
        )

    def verify_integrity(self) -> bool:
        payload = {
            "source": self.source,
            "captured_at": self.captured_at,
            "records": [r.to_dict() for r in self.records],
            "adapter_health": [h.to_dict() for h in self.adapter_health],
            "runtime_version": self.runtime_version,
            "build_revision": self.build_revision,
        }
        return stable_hash(payload) == self.integrity_hash

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.snapshot_id.strip():
            errors.append("snapshot_id must not be empty")
        if not self.captured_at.strip():
            errors.append("captured_at must not be empty")
        if not self.source.strip():
            errors.append("source must not be empty")
        if not self.verify_integrity():
            errors.append("integrity_hash does not match payload — snapshot may be tampered or truncated")
        for r in self.records:
            errors.extend(f"record[{r.observation_id}]: {e}" for e in r.validate())
        return errors

    # ── convenience accessors ─────────────────────────────────────────────────
    def by_source(self, source: str) -> tuple[ObservationRecordSnapshot, ...]:
        return tuple(r for r in self.records if r.source == source)

    def collectors_present(self) -> frozenset[str]:
        return frozenset(r.source for r in self.records)

    def worst_severity(self) -> ObservationSeverity | None:
        if not self.records:
            return None
        return max((ObservationSeverity(r.severity) for r in self.records), key=severity_rank)

    def worst_health(self) -> ObservationHealth | None:
        if not self.records:
            return None
        return max((ObservationHealth(r.health) for r in self.records), key=health_rank)

    # ── (de)serialisation ─────────────────────────────────────────────────────
    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "captured_at": self.captured_at,
            "schema_version": self.schema_version,
            "source": self.source,
            "records": [r.to_dict() for r in self.records],
            "adapter_health": [h.to_dict() for h in self.adapter_health],
            "integrity_hash": self.integrity_hash,
            "runtime_version": self.runtime_version,
            "build_revision": self.build_revision,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RuntimeSnapshotContract:
        return cls(
            snapshot_id=data["snapshot_id"],
            captured_at=data["captured_at"],
            schema_version=data.get("schema_version", SNAPSHOT_CONTRACT_VERSION),
            source=data["source"],
            records=tuple(ObservationRecordSnapshot.from_dict(r) for r in data.get("records") or ()),
            adapter_health=tuple(AdapterHealthSnapshot.from_dict(h) for h in data.get("adapter_health") or ()),
            integrity_hash=data["integrity_hash"],
            runtime_version=data.get("runtime_version", "unknown"),
            build_revision=data.get("build_revision"),
        )


def load_snapshot(path: str) -> RuntimeSnapshotContract:
    """Load a runtime_snapshot.json produced by the Business OS.

    Reads a local file only — this is not a production connection. The
    snapshot itself is the only artifact ever consumed from production.
    """
    import json

    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return RuntimeSnapshotContract.from_dict(data)
