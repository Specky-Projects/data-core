"""Add collection targets.

Revision ID: 0009_collection_targets
Revises: 0008_collector_error_resolution
Create Date: 2026-05-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009_collection_targets"
down_revision: str | None = "0008_collector_error_resolution"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "collection_targets",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("module", sa.String(length=80), nullable=False),
        sa.Column("source_name", sa.String(length=160), nullable=False),
        sa.Column("collector_name", sa.String(length=160), nullable=False),
        sa.Column("target_url", sa.Text(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("module", "source_name", "collector_name", "target_url", name="uq_collection_target_identity"),
    )
    for column in ["module", "source_name", "collector_name", "active"]:
        op.create_index(op.f(f"ix_collection_targets_{column}"), "collection_targets", [column], unique=False)
    op.create_index("ix_collection_targets_active_module", "collection_targets", ["active", "module"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_collection_targets_active_module", table_name="collection_targets")
    for column in ["active", "collector_name", "source_name", "module"]:
        op.drop_index(op.f(f"ix_collection_targets_{column}"), table_name="collection_targets")
    op.drop_table("collection_targets")
