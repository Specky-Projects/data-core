"""telegram observability fields

Revision ID: 0032_telegram_observability
Revises: 0031_sunset_jobs_real_estate, a1b2c3d4e5f6
Create Date: 2026-06-20
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0032_telegram_observability"
down_revision: str | tuple[str, str] | None = (
    "0031_sunset_jobs_real_estate",
    "a1b2c3d4e5f6",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("telegram_delivery_audit", sa.Column("event_type", sa.String(length=80), nullable=True))
    op.add_column("telegram_delivery_audit", sa.Column("strategy", sa.String(length=120), nullable=True))
    op.add_column("telegram_delivery_audit", sa.Column("setup_id", sa.String(length=120), nullable=True))
    op.add_column("telegram_delivery_audit", sa.Column("channel", sa.String(length=80), nullable=True))
    op.add_column("telegram_delivery_audit", sa.Column("severity", sa.String(length=40), nullable=True))
    op.add_column("telegram_delivery_audit", sa.Column("template_name", sa.String(length=120), nullable=True))
    op.add_column("telegram_delivery_audit", sa.Column("correlation_id", sa.String(length=160), nullable=True))
    op.add_column(
        "telegram_delivery_audit",
        sa.Column("payload_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column("telegram_delivery_audit", sa.Column("dedup_key", sa.String(length=255), nullable=True))
    op.create_index(
        "idx_telegram_delivery_audit_event_time",
        "telegram_delivery_audit",
        ["event_type", "created_at"],
    )
    op.create_index(
        "idx_telegram_delivery_audit_strategy_time",
        "telegram_delivery_audit",
        ["strategy", "created_at"],
    )
    op.create_index(
        "idx_telegram_delivery_audit_channel_time",
        "telegram_delivery_audit",
        ["channel", "created_at"],
    )
    op.create_index(
        "idx_telegram_delivery_audit_dedup_time",
        "telegram_delivery_audit",
        ["dedup_key", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_telegram_delivery_audit_dedup_time", table_name="telegram_delivery_audit")
    op.drop_index("idx_telegram_delivery_audit_channel_time", table_name="telegram_delivery_audit")
    op.drop_index("idx_telegram_delivery_audit_strategy_time", table_name="telegram_delivery_audit")
    op.drop_index("idx_telegram_delivery_audit_event_time", table_name="telegram_delivery_audit")
    op.drop_column("telegram_delivery_audit", "dedup_key")
    op.drop_column("telegram_delivery_audit", "payload_summary")
    op.drop_column("telegram_delivery_audit", "correlation_id")
    op.drop_column("telegram_delivery_audit", "template_name")
    op.drop_column("telegram_delivery_audit", "severity")
    op.drop_column("telegram_delivery_audit", "channel")
    op.drop_column("telegram_delivery_audit", "setup_id")
    op.drop_column("telegram_delivery_audit", "strategy")
    op.drop_column("telegram_delivery_audit", "event_type")
