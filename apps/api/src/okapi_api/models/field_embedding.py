"""Field-level vector embedding model for semantic retrieval (architecture doc section 8)."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import ForeignKey, Index, String, types
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from okapi_api.models.base import Base


class FieldEmbedding(Base):
    __tablename__ = "field_embeddings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    field_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("field_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    embedding: Mapped[list[float]] = mapped_column(JSONB, nullable=False)
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    chunk_text: Mapped[str] = mapped_column(types.Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        types.DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    field_version = relationship("FieldVersion")

    __table_args__ = (Index("ix_field_embeddings_version_id", "field_version_id"),)
