"""telegram delivery audit

Revision ID: 0026_telegram_delivery_audit
Revises: 0025_incident_history
Create Date: 2026-06-04
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0026_telegram_delivery_audit"
down_revision = "0025_incident_history"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "telegram_delivery_audit",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("origin", sa.String(length=120), nullable=False),
        sa.Column("trigger", sa.String(length=160), nullable=False),
        sa.Column("bot_id", sa.String(length=64), nullable=True),
        sa.Column("chat_id", sa.String(length=120), nullable=False),
        sa.Column("message_id", sa.String(length=120), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "idx_telegram_delivery_audit_origin_trigger_time",
        "telegram_delivery_audit",
        ["origin", "trigger", "created_at"],
    )
    op.create_index(
        "idx_telegram_delivery_audit_chat_time",
        "telegram_delivery_audit",
        ["chat_id", "created_at"],
    )
    op.create_index(
        "idx_telegram_delivery_audit_status_time",
        "telegram_delivery_audit",
        ["status", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_telegram_delivery_audit_status_time", table_name="telegram_delivery_audit")
    op.drop_index("idx_telegram_delivery_audit_chat_time", table_name="telegram_delivery_audit")
    op.drop_index("idx_telegram_delivery_audit_origin_trigger_time", table_name="telegram_delivery_audit")
    op.drop_table("telegram_delivery_audit")
