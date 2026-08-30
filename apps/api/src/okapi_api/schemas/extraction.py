"""Pydantic schemas for LLM-powered document extraction (architecture doc section 8)."""

import uuid
from typing import Literal

from pydantic import BaseModel, Field


class ExtractedField(BaseModel):
    """A discrete, structured field extracted from unstructured text."""

    field_key: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Structured key name (e.g. 'patient.diagnosis', 'vitals.heart_rate')",
    )
    value: str = Field(..., description="Extracted string representation of value")
    field_type: Literal["text", "number", "date", "code", "boolean"] = Field(
        default="text", description="Data type of the field"
    )
    category: Literal["phi", "clinical", "research", "admin"] = Field(
        default="clinical", description="Regulatory category"
    )
    requires_signoff: bool = Field(
        default=False, description="Whether this field requires human clinician sign-off"
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Extraction model confidence score between 0.0 and 1.0",
    )


class ExtractionRequest(BaseModel):
    """Request payload to extract structured fields from raw document text."""

    raw_text: str = Field(
        ...,
        min_length=1,
        max_length=100000,
        description="Raw unstructured text from clinical note, lab report, or research form",
    )
    document_type: str = Field(
        default="patient_record",
        description="Contextual schema type (e.g. 'patient_record', 'lab_report')",
    )
    auto_register: bool = Field(
        default=False,
        description="If True, directly create/update these fields in the target document",
    )


class ExtractionResponse(BaseModel):
    """Response payload containing all extracted fields and optionally created field IDs."""

    document_id: uuid.UUID
    extracted_fields: list[ExtractedField]
    registered_field_ids: list[uuid.UUID] = Field(default_factory=list)
