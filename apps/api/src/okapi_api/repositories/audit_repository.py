"""AuditRepository — append-only writes and filtered reads of ``audit_log``.

Every gate decision is permanent; there is no update or delete path here
(architecture doc section 4.1).
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from okapi_api.models import AuditLog
from okapi_shared.enums import ActorType, Decision


class AuditRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def record(
        self,
        *,
        actor_id: uuid.UUID,
        actor_type: ActorType,
        action: str,
        decision: Decision,
        reason: str,
        document_id: uuid.UUID | None = None,
        field_id: uuid.UUID | None = None,
    ) -> AuditLog:
        row = AuditLog(
            actor_id=actor_id,
            actor_type=actor_type,
            action=action,
            decision=decision,
            reason=reason,
            document_id=document_id,
            field_id=field_id,
        )
        self._session.add(row)
        self._session.flush()
        return row

    def query(
        self,
        *,
        actor_id: uuid.UUID | None = None,
        actor_type: ActorType | None = None,
        document_id: uuid.UUID | None = None,
        decision: Decision | None = None,
        limit: int = 200,
    ) -> list[AuditLog]:
        stmt = select(AuditLog).order_by(AuditLog.evaluated_at.desc()).limit(limit)
        if actor_id is not None:
            stmt = stmt.where(AuditLog.actor_id == actor_id)
        if actor_type is not None:
            stmt = stmt.where(AuditLog.actor_type == actor_type)
        if document_id is not None:
            stmt = stmt.where(AuditLog.document_id == document_id)
        if decision is not None:
            stmt = stmt.where(AuditLog.decision == decision)
        return list(self._session.scalars(stmt))
