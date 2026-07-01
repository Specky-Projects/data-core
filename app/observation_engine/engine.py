"""Observation Engine — collects ObservationRecords from all adapters."""
from __future__ import annotations

import uuid
from datetime import datetime

from app.capability_orchestrator.contracts import (
    CapabilityKind,
    CapabilityRegistration,
    CapabilityRequest,
    CapabilityResponse,
)
from app.capability_orchestrator.orchestrator import CapabilityOrchestrator
from app.observation_engine.adapters.business_os_adapter import BusinessOSAdapter
from app.observation_engine.adapters.crypto import CryptoAdapter
from app.observation_engine.adapters.docker import DockerAdapter
from app.observation_engine.adapters.infra import InfraAdapter
from app.observation_engine.adapters.mirror import MirrorAdapter
from app.observation_engine.adapters.postgres import PostgresAdapter
from app.observation_engine.adapters.redis_adapter import RedisAdapter
from app.observation_engine.adapters.research import ResearchAdapter
from app.observation_engine.adapters.scheduler import SchedulerAdapter
from app.observation_engine.adapters.telegram import TelegramAdapter
from app.observation_engine.adapters.universal_platform import UniversalPlatformAdapter
from app.observation_engine.contracts import (
    ObservationHealth,
    ObservationRecord,
    ObservationSeverity,
)
from app.scientific_identity.contract import stable_hash


class ObservationEngine:
    name = "observation_engine"

    CAPABILITY_COLLECT_ALL = "observation.collect_all"
    CAPABILITY_COLLECT_PROJECT = "observation.collect_project"
    CAPABILITY_HEALTH = "observation.health"

    def __init__(self) -> None:
        self._adapters = [
            CryptoAdapter(),
            MirrorAdapter(account="mirror"),
            MirrorAdapter(account="specky"),
            MirrorAdapter(account="cav"),
            BusinessOSAdapter(),
            DockerAdapter(),
            PostgresAdapter(),
            RedisAdapter(),
            TelegramAdapter(),
            SchedulerAdapter(),
            InfraAdapter(),
            UniversalPlatformAdapter(),
            ResearchAdapter(),
        ]

    def register(self, orchestrator: CapabilityOrchestrator) -> None:
        """Register all capabilities with the orchestrator."""
        caps = [
            CapabilityRegistration(
                capability_id=self.CAPABILITY_COLLECT_ALL,
                kind=CapabilityKind.OBSERVATION,
                name="Collect All Observations",
                version="1.0.0",
                description="Collects observations from all registered adapters",
                input_schema={},
                output_schema={"records": "list[ObservationRecord]"},
                dependencies=[],
                advisory_only=True,
                owner=self.name,
            ),
            CapabilityRegistration(
                capability_id=self.CAPABILITY_COLLECT_PROJECT,
                kind=CapabilityKind.OBSERVATION,
                name="Collect Project Observations",
                version="1.0.0",
                description="Collects observations filtered by project",
                input_schema={"project": "str"},
                output_schema={"records": "list[ObservationRecord]"},
                dependencies=[],
                advisory_only=True,
                owner=self.name,
            ),
            CapabilityRegistration(
                capability_id=self.CAPABILITY_HEALTH,
                kind=CapabilityKind.OBSERVATION,
                name="Observation Engine Health",
                version="1.0.0",
                description="Returns health status of all adapters",
                input_schema={},
                output_schema={"adapters": "list[dict]"},
                dependencies=[],
                advisory_only=True,
                owner=self.name,
            ),
        ]
        for cap in caps:
            orchestrator.registry.register(cap)
            orchestrator.register_handler(cap.capability_id, self._dispatch(cap.capability_id))

    def _dispatch(self, capability_id: str):
        def handler(request: CapabilityRequest) -> CapabilityResponse:
            lineage_id = str(uuid.uuid4())
            if capability_id == self.CAPABILITY_COLLECT_ALL:
                records = self.collect_all()
                outputs = {"records": [self._record_to_dict(r) for r in records]}
            elif capability_id == self.CAPABILITY_COLLECT_PROJECT:
                project = request.inputs.get("project", "")
                records = [r for r in self.collect_all() if r.project == project]
                outputs = {"records": [self._record_to_dict(r) for r in records]}
            elif capability_id == self.CAPABILITY_HEALTH:
                outputs = {"adapters": self.health()}
            else:
                outputs = {}
            sci_id = stable_hash({"capability": capability_id, "lineage": lineage_id})
            return CapabilityResponse(
                response_id=str(uuid.uuid4()),
                request_id=request.request_id,
                capability_id=capability_id,
                outputs=outputs,
                evidence=[],
                confidence=1.0,
                advisory_only=True,
                lineage_id=lineage_id,
                scientific_id=sci_id,
            )
        return handler

    def collect_all(self) -> list[ObservationRecord]:
        """Collect from every adapter. A single adapter's failure is recorded
        as a degraded ObservationRecord — it never silently vanishes and it
        never cancels the rest of the snapshot (WS6: registrar erro,
        continuar snapshot)."""
        records: list[ObservationRecord] = []
        for adapter in self._adapters:
            try:
                records.extend(adapter.collect())
            except Exception as exc:  # noqa: BLE001 — one adapter's failure must not cancel the snapshot
                ts = datetime.utcnow()
                records.append(
                    ObservationRecord(
                        observation_id=stable_hash({"source": f"{adapter.adapter_name}-error", "ts": ts.isoformat()}),
                        scientific_id=stable_hash({"producer": adapter.adapter_name, "ts": ts.isoformat()}),
                        lineage_id=str(uuid.uuid4()),
                        project=getattr(adapter, "project", "unknown"),
                        domain=getattr(adapter, "domain", "GENERIC"),
                        source=f"{adapter.adapter_name}-collection-error",
                        severity=ObservationSeverity.ERROR,
                        health=ObservationHealth.UNKNOWN,
                        evidence=[f"error:{type(exc).__name__}:{exc}"],
                        metrics={"collection_failed": 1.0},
                        timestamp=ts,
                    )
                )
        return records

    def health(self) -> list[dict]:
        return [adapter.health() for adapter in self._adapters]

    def _record_to_dict(self, record: ObservationRecord) -> dict:
        return {
            "observation_id": record.observation_id,
            "project": record.project,
            "domain": record.domain,
            "source": record.source,
            "severity": str(record.severity),
            "health": str(record.health),
            "metrics": record.metrics,
            "advisory_only": record.advisory_only,
        }
