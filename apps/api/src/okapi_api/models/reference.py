"""``field_references`` — the cross-document dependency graph that powers propagation
(architecture doc sections 4.1 and 4.5). When a source field is edited, every reference
to it is flipped to ``stale``.
"""

import uuid

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from okapi_api.models.base import Base, reference_status_enum
from okapi_shared.enums import ReferenceStatus


class FieldReference(Base):
    __tablename__ = "field_references"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    source_field_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("fields.id", ondelete="CASCADE"), index=True
    )
    referencing_document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE")
    )
    referencing_field_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("fields.id", ondelete="CASCADE")
    )
    status: Mapped[ReferenceStatus] = mapped_column(
        reference_status_enum, default=ReferenceStatus.CURRENT
    )
