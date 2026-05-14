"""Add data governance contract tables.

Revision ID: 0007_data_governance_contracts
Revises: 0006_documentation_lineage
Create Date: 2026-05-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007_data_governance_contracts"
down_revision: str | None = "0006_documentation_lineage"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "data_owners",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("module", sa.String(length=80), nullable=False),
        sa.Column("owner_name", sa.String(length=160), nullable=False),
        sa.Column("technical_contact", sa.String(length=255), nullable=True),
        sa.Column("business_contact", sa.String(length=255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("module", "owner_name", name="uq_data_owner_identity"),
    )
    for column in ["module", "owner_name", "is_active"]:
        op.create_index(op.f(f"ix_data_owners_{column}"), "data_owners", [column], unique=False)

    op.create_table(
        "data_slas",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("module", sa.String(length=80), nullable=False),
        sa.Column("source_name", sa.String(length=160), nullable=True),
        sa.Column("freshness_sla", sa.String(length=120), nullable=False),
        sa.Column("availability_sla", sa.String(length=120), nullable=True),
        sa.Column("quality_sla", sa.String(length=120), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("module", "source_name", name="uq_data_sla_identity"),
    )
    for column in ["module", "source_name", "is_active"]:
        op.create_index(op.f(f"ix_data_slas_{column}"), "data_slas", [column], unique=False)

    op.create_table(
        "data_contracts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("module", sa.String(length=80), nullable=False),
        sa.Column("source_name", sa.String(length=160), nullable=True),
        sa.Column("contract_name", sa.String(length=160), nullable=False),
        sa.Column("contract_version", sa.String(length=40), nullable=False),
        sa.Column("owner_name", sa.String(length=160), nullable=False),
        sa.Column("freshness_sla", sa.String(length=120), nullable=False),
        sa.Column("criticality", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("raw_required", sa.Boolean(), nullable=False),
        sa.Column("lineage_required", sa.Boolean(), nullable=False),
        sa.Column("quality_required", sa.Boolean(), nullable=False),
        sa.Column("schema_rules_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("quality_rules_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("module", "source_name", "contract_name", "contract_version", name="uq_data_contract_identity"),
    )
    for column in ["module", "source_name", "contract_name", "contract_version", "owner_name", "criticality", "status"]:
        op.create_index(op.f(f"ix_data_contracts_{column}"), "data_contracts", [column], unique=False)


def downgrade() -> None:
    for column in ["module", "source_name", "contract_name", "contract_version", "owner_name", "criticality", "status"]:
        op.drop_index(op.f(f"ix_data_contracts_{column}"), table_name="data_contracts")
    op.drop_table("data_contracts")

    for column in ["module", "source_name", "is_active"]:
        op.drop_index(op.f(f"ix_data_slas_{column}"), table_name="data_slas")
    op.drop_table("data_slas")

    for column in ["module", "owner_name", "is_active"]:
        op.drop_index(op.f(f"ix_data_owners_{column}"), table_name="data_owners")
    op.drop_table("data_owners")
