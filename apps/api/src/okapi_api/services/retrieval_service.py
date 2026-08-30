"""RetrievalService — orchestrates the read flow (architecture doc section 5.1).

``Gate.check_fields`` (read) -> ``allowed_field_keys`` -> ``RAGService.retrieve`` over
only those fields. The gate has already written one ``audit_log`` row per field
considered by the time this returns.
"""

from okapi_api.gate.gate import Gate
from okapi_api.models import Document
from okapi_api.repositories.field_repository import FieldRepository
from okapi_api.services.rag_service import RAGService
from okapi_shared.contracts import GateActor


class RetrievalService:
    def __init__(self, gate: Gate, fields: FieldRepository, rag: RAGService) -> None:
        self._gate = gate
        self._fields = fields
        self._rag = rag

    def query(self, *, actor: GateActor, document: Document, question: str) -> dict[str, object]:
        all_fields = self._fields.get_fields_for_document(document.id)
        allowed = self._gate.check_fields(actor=actor, document=document, fields=all_fields)
        withheld = [f.field_key for f in all_fields if f.field_key not in allowed]
        answer = self._rag.retrieve(document.id, allowed, question)
        return {
            "answer": answer["answer"],
            "fields": answer["fields"],
            "allowed_fields": allowed,
            "withheld_fields": withheld,
        }
