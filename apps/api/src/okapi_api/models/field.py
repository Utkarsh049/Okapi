"""``fields`` and ``field_versions`` — the atomic unit and its history (architecture doc 4.1).

``field_versions.parent_version_id`` is an *array* (not a single FK): this is what makes
the lineage a DAG rather than a linked list, and lets a merge commit have two parents
(architecture doc section 4.2).
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from okapi_api.models.base import Base


class Field(Base):
    __tablename__ = "fields"
    __table_args__ = (UniqueConstraint("document_id", "field_key", name="uq_field_doc_key"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    field_key: Mapped[str] = mapped_column(String(200))
    field_type: Mapped[str] = mapped_column(String(50), default="text")
    requires_signoff: Mapped[bool] = mapped_column(Boolean, default=False)
    # Free-form tag (e.g. "phi", "clinical") that ABAC / compliance policies key off.
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=func.now()
    )


class FieldVersion(Base):
    __tablename__ = "field_versions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    field_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("fields.id", ondelete="CASCADE"), index=True
    )
    value: Mapped[str] = mapped_column(Text)
    value_hash: Mapped[str] = mapped_column(String(64))
    parent_version_id: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(Uuid()), default=list)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=func.now()
    )
    is_ai_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    amendment_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    # active | pending_signoff | auto_approved
    status: Mapped[str] = mapped_column(String(30), default="active")
