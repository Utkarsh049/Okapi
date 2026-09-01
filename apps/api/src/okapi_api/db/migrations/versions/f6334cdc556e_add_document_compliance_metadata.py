"""add_document_compliance_metadata

Revision ID: f6334cdc556e
Revises: c081e27bc57a
Create Date: 2026-09-01 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "f6334cdc556e"
down_revision: str | None = "c081e27bc57a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # All nullable: adding a NOT NULL column to an already-populated table requires
    # a server_default to backfill existing rows; nullable avoids that entirely and
    # matches how the merkle-signing columns were added in c081e27bc57a. Unset means
    # "not yet assessed", which every compliance rule already treats the same as an
    # explicit non-matching value.
    op.add_column("documents", sa.Column("consent_status", sa.String(length=20), nullable=True))
    op.add_column(
        "documents",
        sa.Column("consent_purposes", postgresql.ARRAY(sa.String()), nullable=True),
    )
    op.add_column("documents", sa.Column("is_minor", sa.Boolean(), nullable=True))
    op.add_column("documents", sa.Column("parental_consent", sa.Boolean(), nullable=True))
    op.add_column("documents", sa.Column("batch_status", sa.String(length=20), nullable=True))
    op.add_column("documents", sa.Column("is_lot_release", sa.Boolean(), nullable=True))
    op.add_column("documents", sa.Column("is_sae", sa.Boolean(), nullable=True))
    op.add_column("documents", sa.Column("deidentified", sa.Boolean(), nullable=True))
    op.add_column("documents", sa.Column("irb_waiver", sa.Boolean(), nullable=True))
    op.add_column("documents", sa.Column("baa_active", sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column("documents", "baa_active")
    op.drop_column("documents", "irb_waiver")
    op.drop_column("documents", "deidentified")
    op.drop_column("documents", "is_sae")
    op.drop_column("documents", "is_lot_release")
    op.drop_column("documents", "batch_status")
    op.drop_column("documents", "parental_consent")
    op.drop_column("documents", "is_minor")
    op.drop_column("documents", "consent_purposes")
    op.drop_column("documents", "consent_status")
