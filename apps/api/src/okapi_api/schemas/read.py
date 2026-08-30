from pydantic import BaseModel, field_validator

from okapi_api.core.sanitization import sanitize_text


class QueryRequest(BaseModel):
    question: str = "Summarise this document."

    @field_validator("question", mode="before")
    @classmethod
    def sanitize_inputs(cls, v: object) -> object:
        if isinstance(v, str):
            return sanitize_text(v)
        return v


class QueryResponse(BaseModel):
    answer: str
    fields: dict[str, str]
    allowed_fields: list[str]
    withheld_fields: list[str]
