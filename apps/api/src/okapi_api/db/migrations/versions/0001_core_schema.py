"""core schema

Revision ID: 0001_core_schema
Revises:
Create Date: 2026-08-30

Creates the full §4.1 schema: users, documents, fields, field_versions,
lineage_edges, field_references, compliance_rules, audit_log, plus the three
native enum types. Hand-written to match the ORM models exactly; a later
`alembic revision --autogenerate` against a live DB should report no diff.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_core_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

actor_type = postgresql.ENUM("human", "ai_agent", name="actor_type", create_type=False)
decision = postgresql.ENUM("allow", "deny", name="decision", create_type=False)
reference_status = postgresql.ENUM("current", "stale", name="reference_status", create_type=False)


def upgrade() -> None:
    bind = op.get_bind()
    actor_type.create(bind, checkfirst=True)
    decision.create(bind, checkfirst=True)
    reference_status.create(bind, checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("full_name", sa.String(200), nullable=False),
        sa.Column("role", sa.String(50), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("attributes", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "documents",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("doc_type", sa.String(100), nullable=False),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )

    op.create_table(
        "fields",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "document_id",
            sa.Uuid(),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("field_key", sa.String(200), nullable=False),
        sa.Column("field_type", sa.String(50), nullable=False),
        sa.Column("requires_signoff", sa.Boolean(), nullable=False),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("document_id", "field_key", name="uq_field_doc_key"),
    )
    op.create_index("ix_fields_document_id", "fields", ["document_id"])

    op.create_table(
        "field_versions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "field_id", sa.Uuid(), sa.ForeignKey("fields.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("value_hash", sa.String(64), nullable=False),
        sa.Column("parent_version_id", postgresql.ARRAY(sa.Uuid()), nullable=False),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("is_ai_generated", sa.Boolean(), nullable=False),
        sa.Column("amendment_note", sa.Text(), nullable=True),
        sa.Column("status", sa.String(30), nullable=False),
    )
    op.create_index("ix_field_versions_field_id", "field_versions", ["field_id"])

    op.create_table(
        "lineage_edges",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "child_version_id",
            sa.Uuid(),
            sa.ForeignKey("field_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "parent_version_id",
            sa.Uuid(),
            sa.ForeignKey("field_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("edge_hash", sa.String(64), nullable=False),
        sa.UniqueConstraint("child_version_id", "parent_version_id", name="uq_edge_child_parent"),
    )
    op.create_index("ix_lineage_edges_child_version_id", "lineage_edges", ["child_version_id"])
    op.create_index("ix_lineage_edges_parent_version_id", "lineage_edges", ["parent_version_id"])

    op.create_table(
        "field_references",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "source_field_id",
            sa.Uuid(),
            sa.ForeignKey("fields.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "referencing_document_id",
            sa.Uuid(),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "referencing_field_id",
            sa.Uuid(),
            sa.ForeignKey("fields.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", reference_status, nullable=False),
    )
    op.create_index("ix_field_references_source_field_id", "field_references", ["source_field_id"])

    op.create_table(
        "compliance_rules",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("rule_name", sa.String(200), nullable=False),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("opa_package_path", sa.String(200), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("rule_name", name="uq_compliance_rules_rule_name"),
    )

    op.create_table(
        "audit_log",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("actor_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("actor_type", actor_type, nullable=False),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("document_id", sa.Uuid(), sa.ForeignKey("documents.id"), nullable=True),
        sa.Column("field_id", sa.Uuid(), sa.ForeignKey("fields.id"), nullable=True),
        sa.Column("decision", decision, nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "evaluated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )


def downgrade() -> None:
    op.drop_table("audit_log")
    op.drop_table("compliance_rules")
    op.drop_index("ix_field_references_source_field_id", table_name="field_references")
    op.drop_table("field_references")
    op.drop_index("ix_lineage_edges_parent_version_id", table_name="lineage_edges")
    op.drop_index("ix_lineage_edges_child_version_id", table_name="lineage_edges")
    op.drop_table("lineage_edges")
    op.drop_index("ix_field_versions_field_id", table_name="field_versions")
    op.drop_table("field_versions")
    op.drop_index("ix_fields_document_id", table_name="fields")
    op.drop_table("fields")
    op.drop_table("documents")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")

    bind = op.get_bind()
    reference_status.drop(bind, checkfirst=True)
    decision.drop(bind, checkfirst=True)
    actor_type.drop(bind, checkfirst=True)
