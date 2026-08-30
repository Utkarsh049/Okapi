"""Pydantic schemas for AI Form Autofill and Gated Submission workflows (Phase 07)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class DraftedField(BaseModel):
    field_id: uuid.UUID
    field_key: str
    drafted_value: str
    source_field_key: str | None = None
    confidence: float = Field(default=0.90, ge=0.0, le=1.0)
    requires_signoff: bool
    status: str  # "pending_signoff" or "active"


class FormAutofillRequest(BaseModel):
    source_document_ids: list[uuid.UUID]
    target_field_keys: list[str] | None = None


class FormAutofillResponse(BaseModel):
    form_id: uuid.UUID
    drafted_fields: list[DraftedField]
    pending_signoff_count: int


class FormSubmitResponse(BaseModel):
    form_id: uuid.UUID
    status: str  # "submitted"
    submitted_at: datetime
    signed_off_fields: list[str]
