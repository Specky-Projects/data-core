"""Make RAW contract collector-flexible.

Revision ID: 0004_flexible_raw_contract
Revises: 39d33505c86b
Create Date: 2026-05-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_flexible_raw_contract"
down_revision: str | None = "39d33505c86b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("raw_collections", sa.Column("source_type", sa.String(length=80), nullable=True))
    op.add_column(
        "raw_collections",
        sa.Column("collector_name", sa.String(length=160), server_default="unknown", nullable=False),
    )
    op.add_column("raw_collections", sa.Column("target_url", sa.Text(), nullable=True))
    op.execute("UPDATE raw_collections SET target_url = url WHERE target_url IS NULL")
    op.create_index(op.f("ix_raw_collections_source_type"), "raw_collections", ["source_type"], unique=False)
    op.create_index(op.f("ix_raw_collections_collector_name"), "raw_collections", ["collector_name"], unique=False)

    op.add_column("collection_runs", sa.Column("module", sa.String(length=80), nullable=True))
    op.add_column("collection_runs", sa.Column("source_name", sa.String(length=160), nullable=True))
    op.add_column("collection_runs", sa.Column("raw_saved_count", sa.Integer(), server_default="0", nullable=False))
    op.add_column("collection_runs", sa.Column("error_count", sa.Integer(), server_default="0", nullable=False))
    op.add_column(
        "collection_runs",
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
    )
    op.execute("UPDATE collection_runs SET module = domain::text WHERE module IS NULL")
    op.execute("UPDATE collection_runs SET source_name = source WHERE source_name IS NULL")
    op.execute("UPDATE collection_runs SET raw_saved_count = items_collected WHERE raw_saved_count = 0")
    op.create_index(op.f("ix_collection_runs_module"), "collection_runs", ["module"], unique=False)
    op.create_index(op.f("ix_collection_runs_source_name"), "collection_runs", ["source_name"], unique=False)
    op.alter_column("collection_runs", "domain", existing_type=postgresql.ENUM(name="collectordomain"), nullable=True)
    op.alter_column("collection_runs", "source", existing_type=sa.String(length=160), nullable=True)


def downgrade() -> None:
    op.alter_column("collection_runs", "source", existing_type=sa.String(length=160), nullable=False)
    op.alter_column("collection_runs", "domain", existing_type=postgresql.ENUM(name="collectordomain"), nullable=False)
    op.drop_index(op.f("ix_collection_runs_source_name"), table_name="collection_runs")
    op.drop_index(op.f("ix_collection_runs_module"), table_name="collection_runs")
    op.drop_column("collection_runs", "metadata_json")
    op.drop_column("collection_runs", "error_count")
    op.drop_column("collection_runs", "raw_saved_count")
    op.drop_column("collection_runs", "source_name")
    op.drop_column("collection_runs", "module")

    op.drop_index(op.f("ix_raw_collections_collector_name"), table_name="raw_collections")
    op.drop_index(op.f("ix_raw_collections_source_type"), table_name="raw_collections")
    op.drop_column("raw_collections", "target_url")
    op.drop_column("raw_collections", "collector_name")
    op.drop_column("raw_collections", "source_type")
