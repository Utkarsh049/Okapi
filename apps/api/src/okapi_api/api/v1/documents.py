"""Document container + field-scoped write endpoints (architecture doc sections 5.2, 9).

Read/lineage/integrity endpoints are added in milestone 3.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from okapi_api.core.deps import (
    CurrentActor,
    get_document_repo,
    get_edit_service,
    get_field_repo,
    get_versioning_service,
)
from okapi_api.repositories.document_repository import DocumentRepository
from okapi_api.repositories.field_repository import FieldRepository
from okapi_api.schemas.document import DocumentCreate, DocumentRead
from okapi_api.schemas.field import FieldPatch, FieldRead, FieldRegister, VersionRead
from okapi_api.services.edit_service import EditService
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
