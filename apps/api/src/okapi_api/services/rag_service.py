"""RAGService — field-scoped retrieval (architecture doc section 5.1).

STUB for the 50% milestone: no embeddings, no LLM. It returns the current head value
of each permitted field plus a canned summary, so the retrieval flow and its gate
filtering can be demoed end to end. Real pgvector similarity search is deferred.
"""

import uuid

from okapi_api.repositories.field_repository import FieldRepository


class RAGService:
    def __init__(self, fields: FieldRepository) -> None:
        self._fields = fields

    def retrieve(
        self, document_id: uuid.UUID, allowed_field_keys: list[str], question: str
    ) -> dict[str, object]:
        values: dict[str, str] = {}
        for field in self._fields.get_fields_for_document(document_id):
            if field.field_key not in allowed_field_keys:
                continue
            head = self._fields.get_head_version(field.id)
            if head is not None:
                values[field.field_key] = head.value

        if values:
            joined = "; ".join(f"{k}={v}" for k, v in values.items())
            answer = f"[stub RAG] From {len(values)} permitted field(s): {joined}"
        else:
            answer = "[stub RAG] No permitted fields to answer from."

        return {"question": question, "answer": answer, "fields": values}
