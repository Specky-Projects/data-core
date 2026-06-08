"""merge jobs and incident migration branches

Revision ID: 0027_merge_jobs_and_incidents
Revises: 0023_normalized_job_postings, 0026_telegram_delivery_audit
Create Date: 2026-06-05
"""

from __future__ import annotations

revision = "0027_merge_jobs_and_incidents"
down_revision = ("0023_normalized_job_postings", "0026_telegram_delivery_audit")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
