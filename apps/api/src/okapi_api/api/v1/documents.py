"""Document container, field-scoped write, read, lineage, and integrity endpoints
(architecture doc sections 5.1, 5.2, 9).
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from okapi_api.core.deps import (
    CurrentActor,
    get_document_repo,
    get_edit_service,
    get_extraction_service,
    get_field_repo,
    get_integrity_service,
    get_retrieval_service,
    get_versioning_service,
)
from okapi_api.repositories.document_repository import DocumentRepository
from okapi_api.repositories.field_repository import FieldRepository
from okapi_api.schemas.document import DocumentCreate, DocumentRead
from okapi_api.schemas.extraction import ExtractionRequest, ExtractionResponse
from okapi_api.schemas.field import FieldPatch, FieldRead, FieldRegister, VersionRead
from okapi_api.schemas.lineage import LineageGraph
from okapi_api.schemas.read import QueryRequest, QueryResponse
from okapi_api.services.edit_service import EditService
from okapi_api.services.extraction_service import ExtractionService
from okapi_api.services.integrity_service import IntegrityService
from okapi_api.services.retrieval_service import RetrievalService
from okapi_api.services.versioning_service import VersioningService

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
def create_document(
    body: DocumentCreate,
    actor: CurrentActor,
    docs: Annotated[DocumentRepository, Depends(get_document_repo)],
) -> object:
    return docs.create(title=body.title, doc_type=body.doc_type, created_by=uuid.UUID(actor.sub))


@router.post("/{document_id}/fields", response_model=FieldRead, status_code=status.HTTP_201_CREATED)
def register_field(
    document_id: uuid.UUID,
    body: FieldRegister,
    actor: CurrentActor,
    docs: Annotated[DocumentRepository, Depends(get_document_repo)],
    fields: Annotated[FieldRepository, Depends(get_field_repo)],
    versioning: Annotated[VersioningService, Depends(get_versioning_service)],
) -> object:
    if docs.get(document_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "document not found")
    field = fields.register_field(
        document_id=document_id,
        field_key=body.field_key,
        field_type=body.field_type,
        requires_signoff=body.requires_signoff,
        category=body.category,
    )
    if body.value is not None:
        versioning.create_version(
            field_id=field.id, new_value=body.value, actor_id=uuid.UUID(actor.sub)
        )
    return field


@router.post("/{document_id}/extract", response_model=ExtractionResponse)
def extract_document_fields(
    document_id: uuid.UUID,
    body: ExtractionRequest,
    actor: CurrentActor,
    docs: Annotated[DocumentRepository, Depends(get_document_repo)],
    fields: Annotated[FieldRepository, Depends(get_field_repo)],
    versioning: Annotated[VersioningService, Depends(get_versioning_service)],
    extraction: Annotated[ExtractionService, Depends(get_extraction_service)],
) -> object:
    document = docs.get(document_id)
    if document is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "document not found")

    extracted_items = extraction.extract(raw_text=body.raw_text, document_type=body.document_type)
    registered_ids: list[uuid.UUID] = []

    if body.auto_register:
        for item in extracted_items:
            field = fields.register_field(
                document_id=document_id,
                field_key=item.field_key,
                field_type=item.field_type,
                requires_signoff=item.requires_signoff,
                category=item.category,
            )
            versioning.create_version(
                field_id=field.id,
                new_value=item.value,
                actor_id=uuid.UUID(actor.sub),
                is_ai_generated=(actor.actor_type.value == "ai_agent"),
            )
            registered_ids.append(field.id)

    return {
        "document_id": document_id,
        "extracted_fields": extracted_items,
        "registered_field_ids": registered_ids,
    }


@router.patch("/{document_id}/fields/{field_id}", response_model=VersionRead)
def patch_field(
    document_id: uuid.UUID,
    field_id: uuid.UUID,
    body: FieldPatch,
    actor: CurrentActor,
    docs: Annotated[DocumentRepository, Depends(get_document_repo)],
    fields: Annotated[FieldRepository, Depends(get_field_repo)],
    edit: Annotated[EditService, Depends(get_edit_service)],
) -> object:
    document = docs.get(document_id)
    if document is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "document not found")
    field = fields.get_field(field_id)
    if field is None or field.document_id != document_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "field not found")
    return edit.apply_edit(
        actor=actor,
        document=document,
        field=field,
        new_value=body.new_value,
        amendment_note=body.amendment_note,
        parent_version_ids=body.parent_version_ids,
        is_ai_generated=body.is_ai_generated,
    )


@router.post("/{document_id}/query", response_model=QueryResponse)
def query_document(
    document_id: uuid.UUID,
    body: QueryRequest,
    actor: CurrentActor,
    docs: Annotated[DocumentRepository, Depends(get_document_repo)],
    retrieval: Annotated[RetrievalService, Depends(get_retrieval_service)],
) -> object:
    document = docs.get(document_id)
    if document is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "document not found")
    return retrieval.query(actor=actor, document=document, question=body.question)


@router.get("/{document_id}/lineage", response_model=LineageGraph)
def get_lineage(
    document_id: uuid.UUID,
    actor: CurrentActor,
    docs: Annotated[DocumentRepository, Depends(get_document_repo)],
    fields: Annotated[FieldRepository, Depends(get_field_repo)],
) -> object:
    if docs.get(document_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "document not found")
    versions = fields.get_versions_for_document(document_id)
    edges = fields.get_edges_for_document(document_id)
    return {
        "document_id": document_id,
        "nodes": [
            {
                "id": v.id,
                "field_id": v.field_id,
                "value_hash": v.value_hash,
                "status": v.status,
                "is_ai_generated": v.is_ai_generated,
                "parent_version_id": v.parent_version_id,
                "created_at": v.created_at,
            }
            for v in versions
        ],
        "edges": [
            {
                "child_version_id": e.child_version_id,
                "parent_version_id": e.parent_version_id,
                "edge_hash": e.edge_hash,
            }
            for e in edges
        ],
    }


@router.get("/{document_id}/integrity")
def get_integrity(
    document_id: uuid.UUID,
    actor: CurrentActor,
    docs: Annotated[DocumentRepository, Depends(get_document_repo)],
    integrity: Annotated[IntegrityService, Depends(get_integrity_service)],
) -> dict[str, object]:
    if docs.get(document_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "document not found")
    return integrity.verify(document_id)
