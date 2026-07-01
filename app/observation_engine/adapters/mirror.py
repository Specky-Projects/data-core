"""Mirror adapter — real collector, generalized by account.

Reuses the existing trading_edge_outcomes / edge_alert_state tables
(app/modules/crypto/edge/models.py, alert_state_model.py) — the same signal
evaluation data Mirror's own edge analytics already write. No new table, no
new connection path.

Generalization: this ONE adapter class serves Mirror, Specky and CAV per
WS2 — each is a distinct account context, not a distinct integration. When
the underlying tables gain an account-level column, filter by it here; until
then, all accounts observe the same aggregate signal-evaluation view and this
collector says so explicitly in `evidence` rather than fabricating a
per-account split.

MirrorScientificRuntimeBinding.dashboard_snapshot() (app/scientific_consumers/
mirror.py) remains the reuse target for deep per-decision replay/
explainability/ledger coverage — that binding is invoked elsewhere, on
individual decisions already fed through it. This collector's job is the
aggregate operational-health view the snapshot needs, consistent with every
other adapter in this package.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError

from app.observation_engine.contracts import (
    ObservationHealth,
    ObservationRecord,
    ObservationSeverity,
)
from app.scientific_identity.contract import stable_hash
from database.session import SessionLocal

# Accounts sharing this collector, per WS2. "mirror" is the default/aggregate view.
KNOWN_ACCOUNTS: tuple[str, ...] = ("mirror", "specky", "cav")

_ACCOUNT_SEGMENTATION_NOTE = (
    "account-level segmentation pending — trading_edge_outcomes has no account "
    "column yet; this collector reports the shared aggregate signal-evaluation "
    "view for every account until the Business OS wires per-account data"
)


class MirrorAdapter:
    project = "poupi-crypto"
    domain = "CRYPTO"

    def __init__(self, account: str = "mirror") -> None:
        if account not in KNOWN_ACCOUNTS:
            raise ValueError(f"unknown Mirror account: {account!r} (expected one of {KNOWN_ACCOUNTS})")
        self.account = account
        self.adapter_name = "mirror" if account == "mirror" else account

    def collect(self) -> list[ObservationRecord]:
        ts = datetime.utcnow()
        source = "mirror-strategy" if self.account == "mirror" else f"mirror-strategy:{self.account}"
        evidence: list[str] = []
        if self.account != "mirror":
            evidence.append(_ACCOUNT_SEGMENTATION_NOTE)

        try:
            since = ts - timedelta(hours=24)
            with SessionLocal() as db:
                total_outcomes = db.execute(text("SELECT count(*) FROM trading_edge_outcomes")).scalar()
                recent_outcomes = db.execute(
                    text("SELECT count(*) FROM trading_edge_outcomes WHERE signal_at >= :since"),
                    {"since": since},
                ).scalar()
                correct = db.execute(
                    text(
                        "SELECT count(*) FROM trading_edge_outcomes "
                        "WHERE outcome_correct IS TRUE AND signal_at >= :since"
                    ),
                    {"since": since},
                ).scalar()
                evaluated = db.execute(
                    text(
                        "SELECT count(*) FROM trading_edge_outcomes "
                        "WHERE outcome_correct IS NOT NULL AND signal_at >= :since"
                    ),
                    {"since": since},
                ).scalar()
                active_alerts = db.execute(text("SELECT count(*) FROM edge_alert_state")).scalar()

            win_rate = (correct / evaluated) if evaluated else None
            metrics = {
                "total_signal_outcomes": float(total_outcomes or 0),
                "signal_outcomes_24h": float(recent_outcomes or 0),
                "evaluated_24h": float(evaluated or 0),
                "win_rate_24h": round(win_rate, 4) if win_rate is not None else -1.0,
                "active_alert_states": float(active_alerts or 0),
                "reachable": 1.0,
            }
            if (total_outcomes or 0) == 0:
                health = ObservationHealth.UNKNOWN
                severity = ObservationSeverity.INFO
                evidence.append("no signal outcomes present in this environment")
            else:
                health = ObservationHealth.HEALTHY
                severity = ObservationSeverity.INFO
        except ProgrammingError as exc:
            # Expected structural gap (table not migrated in this environment) —
            # not a Mirror operational incident, so this must not read as ERROR.
            metrics = {"reachable": 0.0}
            health = ObservationHealth.UNKNOWN
            severity = ObservationSeverity.INFO
            evidence.append(
                "trading_edge_outcomes/edge_alert_state not present in this environment "
                "(schema gap, not a Mirror incident) — see COLLECTOR_SPECIFICATION.md"
            )
            evidence.append(f"detail:{type(exc).__name__}")
        except Exception as exc:  # noqa: BLE001 — collector must never crash the snapshot
            metrics = {"reachable": 0.0}
            health = ObservationHealth.UNKNOWN
            severity = ObservationSeverity.ERROR
            evidence.append(f"error:{type(exc).__name__}:{exc}")

        return [
            ObservationRecord(
                observation_id=stable_hash({"source": source, "ts": ts.isoformat()}),
                scientific_id=stable_hash({"producer": self.adapter_name, "ts": ts.isoformat()}),
                lineage_id=str(uuid4()),
                project=self.project,
                domain=self.domain,
                source=source,
                severity=severity,
                health=health,
                evidence=evidence,
                metrics=metrics,
                timestamp=ts,
            )
        ]

    def health(self) -> dict:
        try:
            with SessionLocal() as db:
                db.execute(text("SELECT 1 FROM trading_edge_outcomes LIMIT 1"))
            return {"status": "HEALTHY", "adapter": self.adapter_name}
        except Exception as exc:  # noqa: BLE001
            return {"status": "UNKNOWN", "adapter": self.adapter_name, "error": str(exc)}
