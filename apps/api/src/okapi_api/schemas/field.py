"""Pydantic bodies for field registration, edits, and version reads."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class FieldRegister(BaseModel):
    field_key: str
    field_type: str = "text"
    requires_signoff: bool = False
    category: str | None = None
    # Optional initial value — creates version 1 (extraction from raw text is deferred).
    value: str | None = None


class FieldRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    field_key: str
    field_type: str
    requires_signoff: bool
    category: str | None


class FieldPatch(BaseModel):
    new_value: str
    amendment_note: str | None = None
    # Supply two ids to record a merge commit; omit to chain from the current head.
    parent_version_ids: list[uuid.UUID] | None = None
    is_ai_generated: bool = False


class VersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    field_id: uuid.UUID
    value: str
    value_hash: str
    parent_version_id: list[uuid.UUID]
    created_by: uuid.UUID
    created_at: datetime
    is_ai_generated: bool
    amendment_note: str | None
    status: str
