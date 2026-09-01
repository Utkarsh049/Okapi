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
        # Compliance metadata (DPDP/CDSCO/HIPAA) -- previously never reached OPA at
        # all, which is why those regimes could never actually deny anything live.
        "consent_status": document.consent_status,
        "consent_purposes": document.consent_purposes,
        "is_minor": document.is_minor,
        "parental_consent": document.parental_consent,
        "batch_status": document.batch_status,
        "is_lot_release": document.is_lot_release,
        "is_sae": document.is_sae,
        "deidentified": document.deidentified,
        "irb_waiver": document.irb_waiver,
        "baa_active": document.baa_active,
    }


def _compliance_action_meta(document: Document) -> dict[str, object]:
    # field_category must be present as an explicit null, not omitted: abac.rego's
    # object.get(_required_clearance, input.document_metadata.field_category, 0)
    # only falls back to its default when the key reference is defined-but-absent
    # (e.g. null) -- a genuinely missing key makes the reference itself undefined,
    # which makes the whole expression (and so abac.allow) undefined too. Verified
    # empirically against a live OPA instance, not assumed.
    return {"document_id": str(document.id), "doc_type": document.doc_type, "field_category": None}


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

    def check_manage_compliance(self, *, actor: GateActor, document: Document) -> PolicyResult:
        """Raise ``GateDenied`` unless the actor may update this document's
        compliance metadata (consent status, batch status, etc.)."""
        result = self._policy.evaluate(
            PolicyInput(
                actor=actor,
                action=EdgeAction.MANAGE_COMPLIANCE,
                field_key="$document$",
                document_metadata=_compliance_action_meta(document),
            )
        )
        self._audit.record(
            actor_id=uuid.UUID(actor.sub),
            actor_type=actor.actor_type,
            action=EdgeAction.MANAGE_COMPLIANCE.value,
            decision=Decision.ALLOW if result.allow else Decision.DENY,
            reason=result.reason,
            document_id=document.id,
            field_id=None,
        )
        if not result.allow:
            raise GateDenied(result.reason)
        return result
