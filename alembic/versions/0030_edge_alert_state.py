"""edge alert state — Phase 10 Telegram Quant Ops

Revision ID: 0030_edge_alert_state
Revises: 0029_forward_shadow_signals
Create Date: 2026-06-08
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0030_edge_alert_state"
down_revision = "0029_forward_shadow_signals"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "edge_alert_state",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("alert_key", sa.String(length=120), nullable=False),
        sa.Column("last_value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("last_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("alert_key", name="uq_edge_alert_state_key"),
    )
    op.create_index(
        "ix_edge_alert_state_key",
        "edge_alert_state",
        ["alert_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_edge_alert_state_key", table_name="edge_alert_state")
    op.drop_table("edge_alert_state")
