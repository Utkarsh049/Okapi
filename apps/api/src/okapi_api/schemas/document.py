"""Pydantic bodies for the document endpoints."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator

from okapi_api.core.sanitization import sanitize_text


class DocumentCreate(BaseModel):
    title: str
    doc_type: str

    @field_validator("title", "doc_type", mode="before")
    @classmethod
    def sanitize_inputs(cls, v: object) -> object:
        if isinstance(v, str):
            return sanitize_text(v)
        return v


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    doc_type: str
    created_by: uuid.UUID
    created_at: datetime
    # Permissive types on read (plain str/bool, not Literal) so a value that somehow
    # doesn't match the input-side constraints below still reads back cleanly instead
    # of failing to serialize.
    consent_status: str | None = None
    consent_purposes: list[str] | None = None
    is_minor: bool | None = None
    parental_consent: bool | None = None
    batch_status: str | None = None
    is_lot_release: bool | None = None
    is_sae: bool | None = None
    deidentified: bool | None = None
    irb_waiver: bool | None = None
    baa_active: bool | None = None


class DocumentComplianceUpdate(BaseModel):
    """Partial update for a document's compliance metadata — only supplied fields
    are changed (gated to compliance_officer; see Gate.check_manage_compliance).
    """

    consent_status: Literal["active", "withdrawn"] | None = None
    consent_purposes: list[str] | None = None
    is_minor: bool | None = None
    parental_consent: bool | None = None
    batch_status: Literal["in_production", "released", "recalled", "quarantined"] | None = None
    is_lot_release: bool | None = None
    is_sae: bool | None = None
    deidentified: bool | None = None
    irb_waiver: bool | None = None
    baa_active: bool | None = None

    @field_validator("consent_status", "batch_status", mode="before")
    @classmethod
    def sanitize_inputs(cls, v: object) -> object:
        if isinstance(v, str):
            return sanitize_text(v)
        return v
