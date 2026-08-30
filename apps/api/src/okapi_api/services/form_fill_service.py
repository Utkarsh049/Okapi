"""FormFillService — Gated AI Form Auto-Completion & Human Sign-Off Barrier (Phase 07).

Enforces Patent Mechanism 4.6: Fields drafted by AI agents that carry requires_signoff=True
automatically enter status="pending_signoff". The form submission endpoint blocks with 422
Unprocessable Entity if any field remains in a pending_signoff state.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status

from okapi_api.gate.gate import Gate
from okapi_api.repositories.document_repository import DocumentRepository
from okapi_api.repositories.embedding_repository import EmbeddingRepository
from okapi_api.repositories.field_repository import FieldRepository
from okapi_api.schemas.form import (
    DraftedField,
    FormAutofillResponse,
    FormSubmitResponse,
)
from okapi_api.services.embedding_service import EmbeddingService
from okapi_api.services.versioning_service import VersioningService
from okapi_shared.contracts import GateActor


class FormFillService:
    def __init__(
        self,
        gate: Gate,
        docs: DocumentRepository,
        fields: FieldRepository,
        versioning: VersioningService,
        embeddings: EmbeddingRepository | None = None,
        embed_service: EmbeddingService | None = None,
    ) -> None:
        self._gate = gate
        self._docs = docs
        self._fields = fields
        self._versioning = versioning
        self._embeddings = embeddings or EmbeddingRepository(fields._session)
        self._embed_service = embed_service or EmbeddingService()

    def autofill_form(
        self,
        *,
        actor: GateActor,
        form_document_id: uuid.UUID,
        source_document_ids: list[uuid.UUID],
        target_field_keys: list[str] | None = None,
    ) -> FormAutofillResponse:
        """Autofill form fields using semantic extraction and RAG from source records."""
        form_doc = self._docs.get(form_document_id)
        if form_doc is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "form document not found")

        all_target_fields = self._fields.get_fields_for_document(form_document_id)
        if target_field_keys is not None:
            target_fields = [f for f in all_target_fields if f.field_key in target_field_keys]
        else:
            target_fields = all_target_fields

        # Check write permissions on target fields
        allowed_target_keys = self._gate.check_fields(
            actor=actor, document=form_doc, fields=target_fields
        )
        permitted_target_fields = [f for f in target_fields if f.field_key in allowed_target_keys]

        # Gather permitted source fields
        source_field_values: dict[str, str] = {}
        for src_id in source_document_ids:
            src_doc = self._docs.get(src_id)
            if src_doc is None:
                continue
            src_fields = self._fields.get_fields_for_document(src_id)
            allowed_src_keys = self._gate.check_fields(
                actor=actor, document=src_doc, fields=src_fields
            )
            for sf in src_fields:
                if sf.field_key in allowed_src_keys:
                    head = self._fields.get_head_version(sf.id)
                    if head is not None:
                        source_field_values[sf.field_key] = head.value

        drafted_items: list[DraftedField] = []
        pending_count = 0

        for target in permitted_target_fields:
            matched_value: str | None = None
            source_key: str | None = None

            # 1. Exact field key match
            if target.field_key in source_field_values:
                matched_value = source_field_values[target.field_key]
                source_key = target.field_key
            elif source_field_values:
                # 2. Semantic vector match
                query_vec = self._embed_service.embed_text(target.field_key.replace(".", " "))
                best_match: tuple[str, str, float] | None = None
                for sk, sval in source_field_values.items():
                    svec = self._embed_service.embed_text(sval)
                    sim = self._embed_service.cosine_similarity(query_vec, svec)
                    if best_match is None or sim > best_match[2]:
                        best_match = (sk, sval, sim)

                if best_match is not None and best_match[2] > 0.1:
                    source_key, matched_value, _ = best_match

            if matched_value is not None:
                # Determine initial status: pending_signoff for high-impact/signoff fields
                initial_status = "pending_signoff" if target.requires_signoff else "active"
                if initial_status == "pending_signoff":
                    pending_count += 1

                self._versioning.create_version(
                    field_id=target.id,
                    new_value=matched_value,
                    actor_id=uuid.UUID(actor.sub),
                    is_ai_generated=True,
                    status=initial_status,
                    amendment_note=f"AI drafted from source field '{source_key}'",
                )

                drafted_items.append(
                    DraftedField(
                        field_id=target.id,
                        field_key=target.field_key,
                        drafted_value=matched_value,
                        source_field_key=source_key,
                        confidence=0.92,
                        requires_signoff=target.requires_signoff,
                        status=initial_status,
                    )
                )

        return FormAutofillResponse(
            form_id=form_document_id,
            drafted_fields=drafted_items,
            pending_signoff_count=pending_count,
        )

    def submit_form(self, *, actor: GateActor, form_document_id: uuid.UUID) -> FormSubmitResponse:
        """Submit a form, strictly blocking submission if any field is in pending_signoff state."""
        form_doc = self._docs.get(form_document_id)
        if form_doc is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "form document not found")

        fields = self._fields.get_fields_for_document(form_document_id)
        unapproved_fields: list[dict[str, Any]] = []
        approved_keys: list[str] = []

        for f in fields:
            head = self._fields.get_head_version(f.id)
            if head is None:
                unapproved_fields.append(
                    {"field_key": f.field_key, "reason": "No value entered for required field"}
                )
            elif head.status == "pending_signoff":
                unapproved_fields.append(
                    {
                        "field_id": str(f.id),
                        "field_key": f.field_key,
                        "status": head.status,
                        "reason": "Requires human clinician sign-off before form submission",
                    }
                )
            else:
                approved_keys.append(f.field_key)

        if unapproved_fields:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail={
                    "message": "Form submission blocked: required human sign-off missing",
                    "unapproved_fields": unapproved_fields,
                },
            )

        return FormSubmitResponse(
            form_id=form_document_id,
            status="submitted",
            submitted_at=datetime.now(UTC),
            signed_off_fields=approved_keys,
        )
