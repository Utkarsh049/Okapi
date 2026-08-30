"""Audit log query endpoint (architecture doc sections 4.1 and 9).

The audit log is append-only; there is no write endpoint. Filterable by actor,
actor type, document, and decision.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from okapi_api.core.deps import CurrentActor, get_audit_repo
from okapi_api.repositories.audit_repository import AuditRepository
from okapi_api.schemas.audit import AuditRead
from okapi_shared.enums import ActorType, Decision

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", response_model=list[AuditRead])
def query_audit(
    actor: CurrentActor,
    audit: Annotated[AuditRepository, Depends(get_audit_repo)],
    actor_id: uuid.UUID | None = None,
    actor_type: ActorType | None = None,
    document_id: uuid.UUID | None = None,
    decision: Decision | None = None,
    limit: int = 200,
) -> object:
    return audit.query(
        actor_id=actor_id,
        actor_type=actor_type,
        document_id=document_id,
        decision=decision,
        limit=limit,
    )
