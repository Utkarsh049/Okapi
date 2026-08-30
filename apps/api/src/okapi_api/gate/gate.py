"""The Verification & Compliance Gate — the single choke point every service call passes.

Called by the service layer *before* any repository read/write. It builds a
``PolicyInput`` per field, asks the policy client (OPA), writes one ``audit_log`` row
per decision, and either returns the allowed fields (reads) or raises ``GateDenied``
(writes). No repository query runs on a denied path (architecture doc §1, principle 1).
"""

import uuid

from okapi_api.gate.policy_client import PolicyClient
from okapi_api.models import Document, Field
from okapi_api.repositories.audit_repository import AuditRepository
from okapi_shared.contracts import GateActor, PolicyInput, PolicyResult
from okapi_shared.enums import Decision, EdgeAction


class GateDenied(Exception):
    """Raised when OPA denies a write. The API maps it to HTTP 403; the deny is
    already recorded in ``audit_log`` before this is raised."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _doc_meta(document: Document, field: Field) -> dict[str, object]:
    return {
        "document_id": str(document.id),
        "doc_type": document.doc_type,
        "field_category": field.category,
        "requires_signoff": field.requires_signoff,
    }


class Gate:
    def __init__(self, policy_client: PolicyClient, audit: AuditRepository) -> None:
        self._policy = policy_client
        self._audit = audit

    def _decide(
        self, actor: GateActor, action: EdgeAction, document: Document, field: Field
    ) -> PolicyResult:
        result = self._policy.evaluate(
            PolicyInput(
                actor=actor,
                action=action,
                field_key=field.field_key,
                document_metadata=_doc_meta(document, field),
            )
        )
        self._audit.record(
            actor_id=uuid.UUID(actor.sub),
            actor_type=actor.actor_type,
            action=action.value,
            decision=Decision.ALLOW if result.allow else Decision.DENY,
            reason=result.reason,
            document_id=document.id,
            field_id=field.id,
        )
        return result

    def check_write(self, *, actor: GateActor, document: Document, field: Field) -> PolicyResult:
        """Raise ``GateDenied`` unless the actor may write this field."""
        result = self._decide(actor, EdgeAction.WRITE, document, field)
        if not result.allow:
            raise GateDenied(result.reason)
        return result

    def check_signoff(self, *, actor: GateActor, document: Document, field: Field) -> PolicyResult:
        """Raise ``GateDenied`` unless the actor is authorized to sign off on this field."""
        result = self._decide(actor, EdgeAction.SIGNOFF, document, field)
        if not result.allow:
            raise GateDenied(result.reason)
        return result

    def check_fields(
        self, *, actor: GateActor, document: Document, fields: list[Field]
    ) -> list[str]:
        """Return the subset of ``fields`` (by key) the actor may read; audit each."""
        allowed: list[str] = []
        for field in fields:
            if self._decide(actor, EdgeAction.READ, document, field).allow:
                allowed.append(field.field_key)
        return allowed
