"""Pydantic body for audit-log reads (architecture doc section 4.1)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from okapi_shared.enums import ActorType, Decision


class AuditRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    actor_id: uuid.UUID
    actor_type: ActorType
    action: str
    document_id: uuid.UUID | None
    field_id: uuid.UUID | None
    decision: Decision
    reason: str
    evaluated_at: datetime
