"""``users`` — identities and the ABAC attribute bag (architecture doc section 4.1).

``password_hash`` is a prototype convenience so ``POST /auth/token`` can issue a JWT;
a production deployment delegates authentication to an IdP. ``actor_type`` is derived
from ``role`` (``ai_agent`` -> AI, else human).
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from okapi_api.models.base import Base
from okapi_shared.enums import ActorType


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(50))
    password_hash: Mapped[str] = mapped_column(String(255))
    attributes: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    @property
    def actor_type(self) -> ActorType:
        return ActorType.AI_AGENT if self.role == "ai_agent" else ActorType.HUMAN
