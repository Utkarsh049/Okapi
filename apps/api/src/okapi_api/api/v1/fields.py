"""Field-level actions not nested under a document path (architecture doc section 9).

``POST /fields/{field_id}/signoff`` is the human approval action for a gated field:
it passes through Gate.check_signoff, clears the head version's ``pending_signoff``
status, and activates the version.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from okapi_api.core.deps import (
    CurrentActor,
    get_document_repo,
    get_field_repo,
    get_gate,
)
from okapi_api.gate.gate import Gate
from okapi_api.repositories.document_repository import DocumentRepository
from okapi_api.repositories.field_repository import FieldRepository
from okapi_api.schemas.field import VersionRead

router = APIRouter(prefix="/fields", tags=["fields"])


@router.post("/{field_id}/signoff", response_model=VersionRead)
def sign_off_field(
    field_id: uuid.UUID,
    actor: CurrentActor,
    docs: Annotated[DocumentRepository, Depends(get_document_repo)],
    fields: Annotated[FieldRepository, Depends(get_field_repo)],
    gate: Annotated[Gate, Depends(get_gate)],
) -> object:
    field = fields.get_field(field_id)
    if field is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "field not found")
    document = docs.get(field.document_id)
    if document is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "document not found")

    head = fields.get_head_version(field_id)
    if head is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "field has no version to sign off")

    # Evaluate authorization through the Gate before updating status
    gate.check_signoff(actor=actor, document=document, field=field)

    fields.set_version_status(head.id, "active")
    head.status = "active"
    return head
