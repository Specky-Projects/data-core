"""Add pipeline_runs and pipeline_failures tables for operational observability.

Revision ID: 0015_pipeline_observability
Revises: 0014_uniq_candle_identity
Create Date: 2026-05-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0015_pipeline_observability"
down_revision: str | None = "0014_uniq_candle_identity"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── pipeline_runs ─────────────────────────────────────────────────────────
    op.create_table(
        "pipeline_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("domain", sa.String(64), nullable=False),
        sa.Column("stage", sa.String(32), nullable=False),
        sa.Column("source_name", sa.String(128), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Float, nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="running"),
        sa.Column("items_input", sa.Integer, nullable=False, server_default="0"),
        sa.Column("items_processed", sa.Integer, nullable=False, server_default="0"),
        sa.Column("items_skipped", sa.Integer, nullable=False, server_default="0"),
        sa.Column("items_error", sa.Integer, nullable=False, server_default="0"),
        sa.Column("trigger", sa.String(32), nullable=True),
        sa.Column("extra_json", postgresql.JSONB, nullable=True),
    )
    op.create_index("ix_pipeline_runs_domain", "pipeline_runs", ["domain"])
    op.create_index("ix_pipeline_runs_stage", "pipeline_runs", ["stage"])
    op.create_index("ix_pipeline_runs_status_started", "pipeline_runs", ["status", "started_at"])
    op.create_index(
        "ix_pipeline_runs_domain_stage_started",
        "pipeline_runs",
        ["domain", "stage", "started_at"],
    )

    # ── pipeline_failures ─────────────────────────────────────────────────────
    op.create_table(
        "pipeline_failures",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("pipeline_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("domain", sa.String(64), nullable=False),
        sa.Column("stage", sa.String(32), nullable=False),
        sa.Column("error_type", sa.String(128), nullable=False),
        sa.Column("error_message", sa.Text, nullable=False),
        sa.Column("traceback", sa.Text, nullable=True),
        sa.Column("item_id", sa.String(256), nullable=True),
        sa.Column("item_context", postgresql.JSONB, nullable=True),
        sa.Column("retry_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("is_terminal", sa.Boolean, nullable=False, server_default="false"),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index("ix_pipeline_failures_run_id", "pipeline_failures", ["run_id"])
    op.create_index("ix_pipeline_failures_domain", "pipeline_failures", ["domain"])
    op.create_index(
        "ix_pipeline_failures_domain_occurred",
        "pipeline_failures",
        ["domain", "occurred_at"],
    )
    op.create_index(
        "ix_pipeline_failures_error_type",
        "pipeline_failures",
        ["error_type", "occurred_at"],
    )


def downgrade() -> None:
    op.drop_table("pipeline_failures")
    op.drop_table("pipeline_runs")
