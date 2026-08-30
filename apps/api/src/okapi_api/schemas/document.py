"""Pydantic bodies for the document endpoints."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DocumentCreate(BaseModel):
    title: str
    doc_type: str


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    doc_type: str
    created_by: uuid.UUID
    created_at: datetime
