"""Field-level actions not nested under a document path (architecture doc section 9).

``POST /fields/{field_id}/signoff`` is the human approval action for a gated field:
it clears the head version's ``pending_signoff`` status and records the approval.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from okapi_api.core.deps import CurrentActor, get_audit_repo, get_field_repo
from okapi_api.repositories.audit_repository import AuditRepository
from okapi_api.repositories.field_repository import FieldRepository
from okapi_api.schemas.field import VersionRead
from okapi_shared.enums import Decision

router = APIRouter(prefix="/fields", tags=["fields"])


@router.post("/{field_id}/signoff", response_model=VersionRead)
def sign_off_field(
    field_id: uuid.UUID,
    actor: CurrentActor,
    fields: Annotated[FieldRepository, Depends(get_field_repo)],
    audit: Annotated[AuditRepository, Depends(get_audit_repo)],
) -> object:
    field = fields.get_field(field_id)
    if field is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "field not found")
    head = fields.get_head_version(field_id)
    if head is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "field has no version to sign off")
    fields.set_version_status(head.id, "active")
    head.status = "active"
    audit.record(
        actor_id=uuid.UUID(actor.sub),
        actor_type=actor.actor_type,
        action="signoff",
        decision=Decision.ALLOW,
        reason="human sign-off",
        document_id=field.document_id,
        field_id=field.id,
    )
    return head
