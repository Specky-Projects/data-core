"""observer_snapshot_runs table — Business OS 6.0 Observer Framework Phase 2 (WS1+WS2)

Revision ID: 0105_observer_snapshot_runs
Revises: 0104_universal_execution_log
Create Date: 2026-07-01

One row per Observer Framework cycle (snapshot -> diagnosis -> certification).
Follows the same shape as watchdog_runs: timestamp + JSONB blobs, never
overwritten — every cycle is a new row, giving a full auditable history.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "0105_observer_snapshot_runs"
down_revision = "0104_universal_execution_log"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "observer_snapshot_runs",
        sa.Column("id", sa.Integer(), nullable=False, primary_key=True, autoincrement=True),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("snapshot_id", sa.String(128), nullable=False),
        sa.Column("integrity_hash", sa.String(128), nullable=False),
        sa.Column("runtime_version", sa.String(64), nullable=False),
        sa.Column("build_revision", sa.String(64), nullable=True),
        sa.Column("overall_health", sa.String(16), nullable=False),
        sa.Column("overall_severity", sa.String(16), nullable=False),
        sa.Column("operational_score", sa.Float(), nullable=False),
        sa.Column("classification", sa.String(24), nullable=False),
        sa.Column("incident_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("new_incident_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("resolved_incident_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("snapshot_json", JSONB, nullable=False),
        sa.Column("diagnosis_json", JSONB, nullable=False),
        sa.Column("validation_json", JSONB, nullable=False),
        sa.Column("certification_json", JSONB, nullable=False),
        sa.Column("telegram_sent", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("error_message", sa.Text(), nullable=True),
    )

    op.create_index("ix_observer_snapshot_runs_captured_at", "observer_snapshot_runs", ["captured_at"])
    op.create_index("ix_observer_snapshot_runs_snapshot_id", "observer_snapshot_runs", ["snapshot_id"])


def downgrade() -> None:
    op.drop_table("observer_snapshot_runs")
