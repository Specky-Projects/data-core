"""WS3 — Telegram Adapter.

The universal interface of the Business OS. Inbound Telegram messages (a
question, an ack, a command) become observations; outbound artifacts (daily
brief, alerts, diagnostics, roadmaps, certifications) are *rendered* here but
never decided here. No business logic lives in Telegram — commands are resolved
against the Capability Registry by the orchestrator, not by this adapter.
"""
from __future__ import annotations

from typing import Any

from app.universal_platform.adapters.base import BaseAdapter
from app.universal_platform.events import Severity, UniversalEvent

# Outbound artifact kinds Telegram is allowed to deliver (render-only).
OUTBOUND_KINDS = (
    "daily_brief",
    "alert",
    "diagnostic",
    "roadmap",
    "certification",
    "answer",
)

# Inbound message kinds Telegram can observe.
INBOUND_KINDS = (
    "message",
    "command",
    "question",
    "ack",
)


class TelegramAdapter(BaseAdapter):
    PROJECT = "telegram"
    DOMAIN = "TELEGRAM"

    def to_event(self, raw: dict[str, Any]) -> UniversalEvent:
        kind = str(raw.get("kind") or "message")
        event_type = f"telegram.{kind}"
        entity_id = str(raw.get("chat_id") or raw.get("entity_id") or "telegram-default")
        occurred_at = str(raw.get("occurred_at") or raw.get("received_at") or "")
        # A command references a capability but never executes it here.
        command = raw.get("command")
        metadata: dict[str, Any] = {"kind": kind}
        if command:
            metadata["capability_ref"] = str(command)
        return UniversalEvent.create(
            project=self.PROJECT,
            domain=self.DOMAIN,
            event_type=event_type,
            entity_id=entity_id,
            occurred_at=occurred_at,
            confidence=1.0,
            severity=raw.get("severity", Severity.INFO),
            evidence=raw.get("evidence", ()),
            metrics={},
            payload=dict(raw),
            metadata=metadata,
        )

    @staticmethod
    def render_outbound(kind: str, title: str, body: str) -> dict[str, Any]:
        """Prepare (but do not send) an outbound artifact. Advisory + shadow."""
        assert kind in OUTBOUND_KINDS, f"unsupported outbound kind: {kind}"
        return {
            "kind": kind,
            "title": title,
            "body": body,
            "delivered": False,        # SHADOW: never actually transmitted here
            "advisory_only": True,
        }
