"""Request/response contracts for the Verification & Compliance Gate.

These are the exact shapes exchanged with OPA (architecture doc sections 6 and 6.1):
the service layer builds a :class:`PolicyInput`, ``PolicyClient`` POSTs it to the OPA
sidecar, and OPA returns a :class:`PolicyResult`.
"""

from pydantic import BaseModel, Field

from okapi_shared.enums import ActorType, EdgeAction


class GateActor(BaseModel):
    """Identity presented to the gate, derived from the caller's JWT claims."""

    sub: str
    role: str
    actor_type: ActorType
    # e.g. {"department": "cardiology", "clearance_level": 3} — ABAC keys off these.
    attributes: dict[str, object] = Field(default_factory=dict)
    acting_on_behalf_of: str | None = None


class PolicyInput(BaseModel):
    """Everything OPA needs to decide a single field-scoped action."""

    actor: GateActor
    action: EdgeAction
    field_key: str
    document_metadata: dict[str, object] = Field(default_factory=dict)


class PolicyResult(BaseModel):
    """OPA's answer. ``allowed_fields`` is the subset the caller may see or touch."""

    allow: bool
    allowed_fields: list[str] = Field(default_factory=list)
    reason: str
