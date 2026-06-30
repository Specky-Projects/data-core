"""universal_executions table — Business OS 5.0 Universal Execution Log

Revision ID: 0104_universal_execution_log
Revises: 0033_merge_wnba_telegram
Create Date: 2026-06-29

The UEL is the canonical flight-recorder for the entire Business OS ecosystem.
Every project (Crypto, Baby, Sinalo, future) emits executions into this single
immutable table. None own it. This migration creates the core table and all
indexes required for dashboard and lineage queries.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID

from alembic import op

revision = "0104_universal_execution_log"
down_revision = "0033_merge_wnba_telegram"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "universal_executions",

        # ── Identity ──────────────────────────────────────────────────────────
        sa.Column("id", PG_UUID(as_uuid=True),
                  nullable=False, primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("execution_id", sa.String(64), nullable=False),
        sa.Column("schema_version", sa.String(40), nullable=False),

        # ── Lineage ───────────────────────────────────────────────────────────
        sa.Column("mission_id", sa.String(128), nullable=True),
        sa.Column("portfolio_id", sa.String(128), nullable=True),
        sa.Column("project_id", sa.String(64), nullable=False),
        sa.Column("capability_id", sa.String(128), nullable=False),
        sa.Column("lineage", JSONB, nullable=False, server_default="'{}'"),

        # ── Surface & type ────────────────────────────────────────────────────
        sa.Column("execution_surface", sa.String(64), nullable=False),
        sa.Column("execution_type", sa.String(64), nullable=False),

        # ── Actors ────────────────────────────────────────────────────────────
        sa.Column("actor", sa.String(128), nullable=True),
        sa.Column("planner", sa.String(128), nullable=True),
        sa.Column("reviewer", sa.String(128), nullable=True),
        sa.Column("executor", sa.String(128), nullable=True),

        # ── Correlation ───────────────────────────────────────────────────────
        sa.Column("execution_plan_id", sa.String(128), nullable=True),
        sa.Column("correlation_id", sa.String(128), nullable=True),
        sa.Column("parent_execution_id", sa.String(64), nullable=True),
        sa.Column("relation", sa.String(32), nullable=True),

        # ── Timing ────────────────────────────────────────────────────────────
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Float(), nullable=False, server_default="0.0"),

        # ── State ─────────────────────────────────────────────────────────────
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("decision", JSONB, nullable=False, server_default="'{}'"),
        sa.Column("outcome", JSONB, nullable=False, server_default="'{}'"),

        # ── Evidence & learning ───────────────────────────────────────────────
        sa.Column("evidence_ids", JSONB, nullable=False, server_default="'[]'"),
        sa.Column("knowledge_ids", JSONB, nullable=False, server_default="'[]'"),
        sa.Column("learning_ids", JSONB, nullable=False, server_default="'[]'"),

        # ── Metrics ───────────────────────────────────────────────────────────
        sa.Column("metrics", JSONB, nullable=False, server_default="'{}'"),

        # ── Tags ──────────────────────────────────────────────────────────────
        sa.Column("tags", JSONB, nullable=False, server_default="'{}'"),

        # ── UEL version ───────────────────────────────────────────────────────
        sa.Column("uel_version", sa.String(80), nullable=False),

        # ── Audit timestamps ──────────────────────────────────────────────────
        sa.Column("created_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.text("now()")),
    )

    # ── Unique constraint ─────────────────────────────────────────────────────
    op.create_index(
        "uq_uel_execution_id",
        "universal_executions",
        ["execution_id"],
        unique=True,
    )

    # ── Core lookup indexes ───────────────────────────────────────────────────
    op.create_index("ix_uel_project_id", "universal_executions", ["project_id"])
    op.create_index("ix_uel_capability_id", "universal_executions", ["capability_id"])
    op.create_index("ix_uel_mission_id", "universal_executions", ["mission_id"])
    op.create_index("ix_uel_status", "universal_executions", ["status"])
    op.create_index("ix_uel_timestamp", "universal_executions", ["timestamp"])
    op.create_index("ix_uel_actor", "universal_executions", ["actor"])
    op.create_index("ix_uel_correlation_id", "universal_executions", ["correlation_id"])
    op.create_index("ix_uel_parent_execution_id", "universal_executions", ["parent_execution_id"])

    # ── Composite indexes for dashboard and lineage queries ───────────────────
    op.create_index(
        "ix_uel_project_surface",
        "universal_executions",
        ["project_id", "execution_surface"],
    )
    op.create_index(
        "ix_uel_project_status",
        "universal_executions",
        ["project_id", "status"],
    )
    op.create_index(
        "ix_uel_mission_capability",
        "universal_executions",
        ["mission_id", "capability_id"],
    )
    op.create_index(
        "ix_uel_timestamp_status",
        "universal_executions",
        ["timestamp", "status"],
    )

    # ── Partial index: active executions (not finished) ───────────────────────
    op.create_index(
        "ix_uel_active",
        "universal_executions",
        ["project_id", "timestamp"],
        postgresql_where=sa.text("status IN ('planned', 'approved', 'running')"),
    )


def downgrade() -> None:
    op.drop_table("universal_executions")
