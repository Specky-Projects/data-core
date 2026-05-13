"""Initial data core schema.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-05-13
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

collector_domain = postgresql.ENUM(
    "real_estate",
    "ecommerce",
    "crypto",
    "sports_betting",
    name="collectordomain",
)
run_status = postgresql.ENUM(
    "pending",
    "running",
    "success",
    "failed",
    "partial",
    name="runstatus",
)


def upgrade() -> None:
    collector_domain.create(op.get_bind(), checkfirst=True)
    run_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "collector_definitions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("domain", collector_domain, nullable=False),
        sa.Column("source", sa.String(length=160), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_collector_definitions_domain", "collector_definitions", ["domain"])
    op.create_index("ix_collector_definitions_name", "collector_definitions", ["name"], unique=True)
    op.create_index("ix_collector_definitions_source", "collector_definitions", ["source"])

    op.create_table(
        "collection_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("collector_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("collector_name", sa.String(length=160), nullable=False),
        sa.Column("domain", collector_domain, nullable=False),
        sa.Column("source", sa.String(length=160), nullable=False),
        sa.Column("status", run_status, nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("items_collected", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["collector_id"], ["collector_definitions.id"]),
    )
    op.create_index("ix_collection_runs_collector_name", "collection_runs", ["collector_name"])
    op.create_index(
        "ix_collection_runs_collector_started",
        "collection_runs",
        ["collector_name", "started_at"],
    )
    op.create_index("ix_collection_runs_domain", "collection_runs", ["domain"])
    op.create_index("ix_collection_runs_source", "collection_runs", ["source"])
    op.create_index("ix_collection_runs_status", "collection_runs", ["status"])

    op.create_table(
        "collected_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("collector_name", sa.String(length=160), nullable=False),
        sa.Column("domain", collector_domain, nullable=False),
        sa.Column("source", sa.String(length=160), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["run_id"], ["collection_runs.id"]),
        sa.UniqueConstraint(
            "collector_name",
            "source",
            "external_id",
            "payload_hash",
            name="uq_record_identity_snapshot",
        ),
    )
    op.create_index(
        "ix_collected_records_domain_collected",
        "collected_records",
        ["domain", "collected_at"],
    )
    op.create_index("ix_collected_records_collector_name", "collected_records", ["collector_name"])
    op.create_index("ix_collected_records_domain", "collected_records", ["domain"])
    op.create_index("ix_collected_records_payload_hash", "collected_records", ["payload_hash"])
    op.create_index("ix_collected_records_source", "collected_records", ["source"])

    op.create_table(
        "collector_errors",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("collector_name", sa.String(length=160), nullable=False),
        sa.Column("error_type", sa.String(length=160), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("traceback", sa.Text(), nullable=True),
        sa.Column("context", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["run_id"], ["collection_runs.id"]),
    )
    op.create_index("ix_collector_errors_collector_name", "collector_errors", ["collector_name"])


def downgrade() -> None:
    op.drop_index("ix_collector_errors_collector_name", table_name="collector_errors")
    op.drop_table("collector_errors")

    op.drop_index("ix_collected_records_source", table_name="collected_records")
    op.drop_index("ix_collected_records_payload_hash", table_name="collected_records")
    op.drop_index("ix_collected_records_domain", table_name="collected_records")
    op.drop_index("ix_collected_records_collector_name", table_name="collected_records")
    op.drop_index("ix_collected_records_domain_collected", table_name="collected_records")
    op.drop_table("collected_records")

    op.drop_index("ix_collection_runs_status", table_name="collection_runs")
    op.drop_index("ix_collection_runs_source", table_name="collection_runs")
    op.drop_index("ix_collection_runs_domain", table_name="collection_runs")
    op.drop_index("ix_collection_runs_collector_started", table_name="collection_runs")
    op.drop_index("ix_collection_runs_collector_name", table_name="collection_runs")
    op.drop_table("collection_runs")

    op.drop_index("ix_collector_definitions_source", table_name="collector_definitions")
    op.drop_index("ix_collector_definitions_name", table_name="collector_definitions")
    op.drop_index("ix_collector_definitions_domain", table_name="collector_definitions")
    op.drop_table("collector_definitions")

    run_status.drop(op.get_bind(), checkfirst=True)
    collector_domain.drop(op.get_bind(), checkfirst=True)

