"""FastAPI dependency wiring.

Everything the routers need is assembled here by constructor injection so the pieces
stay unit-testable with mocks (architecture doc section 10). Direction of dependency
is strictly downward: routers -> services -> gate/repositories.
"""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from okapi_api.core.security import decode_access_token
from okapi_api.db.session import get_session
from okapi_api.gate.gate import Gate
from okapi_api.gate.policy_client import OpaPolicyClient, PolicyClient
from okapi_api.repositories.audit_repository import AuditRepository
from okapi_api.repositories.document_repository import DocumentRepository
from okapi_api.repositories.field_repository import FieldRepository
from okapi_api.repositories.user_repository import UserRepository
from okapi_api.services.edit_service import EditService
from okapi_api.services.lineage_service import LineageService
from okapi_api.services.propagation_service import PropagationService
from okapi_api.services.versioning_service import VersioningService
from okapi_shared.contracts import GateActor
from okapi_shared.enums import ActorType

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")

DbSession = Annotated[Session, Depends(get_session)]


# --- repositories -----------------------------------------------------------
def get_user_repo(db: DbSession) -> UserRepository:
    return UserRepository(db)


def get_document_repo(db: DbSession) -> DocumentRepository:
    return DocumentRepository(db)


def get_field_repo(db: DbSession) -> FieldRepository:
    return FieldRepository(db)


def get_audit_repo(db: DbSession) -> AuditRepository:
    return AuditRepository(db)


# --- identity -------------------------------------------------------------------
def get_current_actor(token: Annotated[str, Depends(oauth2_scheme)]) -> GateActor:
    try:
        claims = decode_access_token(token)
        return GateActor(
            sub=str(claims["sub"]),
            role=str(claims["role"]),
            actor_type=ActorType(claims["actor_type"]),
            attributes=dict(claims.get("attributes") or {}),
            acting_on_behalf_of=claims.get("acting_on_behalf_of"),
        )
    except (KeyError, ValueError) as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"invalid token: {exc}") from exc
    except Exception as exc:  # noqa: BLE001 - jwt errors -> 401
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid token") from exc


CurrentActor = Annotated[GateActor, Depends(get_current_actor)]


# --- gate + services ----------------------------------------------------------
def get_policy_client() -> PolicyClient:
    return OpaPolicyClient()


def get_gate(
    policy_client: Annotated[PolicyClient, Depends(get_policy_client)],
    audit: Annotated[AuditRepository, Depends(get_audit_repo)],
) -> Gate:
    return Gate(policy_client, audit)


def get_edit_service(
    gate: Annotated[Gate, Depends(get_gate)],
    fields: Annotated[FieldRepository, Depends(get_field_repo)],
) -> EditService:
    return EditService(
        gate,
        VersioningService(fields),
        LineageService(fields),
        PropagationService(fields),
        fields,
    )


def get_versioning_service(
    fields: Annotated[FieldRepository, Depends(get_field_repo)],
) -> VersioningService:
    return VersioningService(fields)
