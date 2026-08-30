"""Pydantic bodies for the field-scoped read flow (architecture doc section 5.1)."""

from pydantic import BaseModel


class QueryRequest(BaseModel):
    question: str = "Summarise this document."


class QueryResponse(BaseModel):
    answer: str
    fields: dict[str, str]
    allowed_fields: list[str]
    withheld_fields: list[str]
