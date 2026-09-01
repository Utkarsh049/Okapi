"""``documents`` — containers only; no versioned content lives here (architecture doc 4.1)."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import ARRAY
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
    last_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Compliance metadata (DPDP/CDSCO/HIPAA — architecture doc §6). Bookkeeping about
    # the record, not content: mutated directly like merkle_root above, not versioned
    # like field values. Nullable throughout: unset means "not yet assessed", which
    # every compliance rule already treats the same as an explicit false/not-matching
    # value (see Gate._doc_meta for how these reach OPA).
    consent_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    consent_purposes: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    is_minor: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    parental_consent: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    batch_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    is_lot_release: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    is_sae: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    deidentified: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    irb_waiver: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    baa_active: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
