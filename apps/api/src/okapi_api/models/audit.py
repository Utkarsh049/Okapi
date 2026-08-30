"""``audit_log`` — every gate decision, permanent and append-only (architecture doc 4.1).

One row per field considered on every read and write. ``actor_type`` distinguishes an
AI-originated action from a human one (required for mechanism 4.6).
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from okapi_api.models.base import Base, actor_type_enum, decision_enum
from okapi_shared.enums import ActorType, Decision


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    actor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    actor_type: Mapped[ActorType] = mapped_column(actor_type_enum)
    action: Mapped[str] = mapped_column(String(50))
    document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("documents.id"), nullable=True)
    field_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("fields.id"), nullable=True)
    decision: Mapped[Decision] = mapped_column(decision_enum)
    reason: Mapped[str] = mapped_column(Text)
    evaluated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
