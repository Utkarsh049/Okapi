"""Pydantic bodies for the document endpoints."""

import uuid
from datetime import datetime

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
