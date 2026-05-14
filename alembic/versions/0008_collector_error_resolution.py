"""Add collector error resolution fields.

Revision ID: 0008_collector_error_resolution
Revises: 0007_data_governance_contracts
Create Date: 2026-05-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_collector_error_resolution"
down_revision: str | None = "0007_data_governance_contracts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("collector_errors", sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("collector_errors", sa.Column("resolution_note", sa.Text(), nullable=True))
    op.create_index(op.f("ix_collector_errors_resolved_at"), "collector_errors", ["resolved_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_collector_errors_resolved_at"), table_name="collector_errors")
    op.drop_column("collector_errors", "resolution_note")
    op.drop_column("collector_errors", "resolved_at")
