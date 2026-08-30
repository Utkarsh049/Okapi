"""``documents`` — containers only; no versioned content lives here (architecture doc 4.1)."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from okapi_api.models.base import Base


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(500))
    doc_type: Mapped[str] = mapped_column(String(100))
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    merkle_root: Mapped[str | None] = mapped_column(String(64), nullable=True)
    merkle_signature: Mapped[str | None] = mapped_column(String(128), nullable=True)
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
