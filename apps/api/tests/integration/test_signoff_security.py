"""Integration security tests for Gated Sign-off authorization enforcement (Phase 02)."""

import uuid

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session
from starlette.testclient import TestClient

from okapi_api.core.deps import get_policy_client
from okapi_api.core.hashing import hash_value
from okapi_api.core.security import hash_password
from okapi_api.main import app
from okapi_api.models import Document, Field, FieldVersion, User
from okapi_shared.contracts import PolicyInput, PolicyResult
from okapi_shared.enums import EdgeAction

pytestmark = pytest.mark.integration

API = "/api/v1"


class RbacPolicyClient:
    """Evaluates role rules mirroring rbac.rego for deterministic integration testing."""

    def evaluate(self, policy_input: PolicyInput) -> PolicyResult:
        role = policy_input.actor.role
        action = policy_input.action
        category = str(policy_input.document_metadata.get("field_category", ""))

        if role == "compliance_officer" and action in {EdgeAction.READ, EdgeAction.SIGNOFF}:
            return PolicyResult(allow=True, reason="allowed by compliance_officer rbac")
        if (
            role == "clinician"
            and action in {EdgeAction.READ, EdgeAction.WRITE, EdgeAction.SIGNOFF}
            and category in {"clinical", "phi"}
        ):
            return PolicyResult(allow=True, reason="allowed by clinician rbac")
        if role == "researcher" and action == EdgeAction.READ and category == "research":
            return PolicyResult(allow=True, reason="allowed by researcher rbac")
        return PolicyResult(allow=False, reason=f"denied by rbac (role={role}, action={action})")


@pytest.fixture
def rbac_api_client(api_client: TestClient) -> TestClient:
    app.dependency_overrides[get_policy_client] = lambda: RbacPolicyClient()
    return api_client


def _seed_user(engine: Engine, role: str, clearance: int, dept: str) -> tuple[str, str]:
    email = f"{role}-{uuid.uuid4()}@okapi.dev"
    password = "pass"
    with Session(engine) as session:
        session.add(
            User(
                email=email,
                full_name=f"Test {role.capitalize()}",
                role=role,
                password_hash=hash_password(password),
                attributes={"clearance_level": clearance, "department": dept},
            )
        )
        session.commit()
    return email, password


def _create_gated_field(engine: Engine, category: str = "phi") -> tuple[uuid.UUID, uuid.UUID]:
    with Session(engine) as session:
        owner = User(
            email=f"owner-{uuid.uuid4()}@okapi.dev",
            full_name="Doc Owner",
            role="clinician",
            password_hash=hash_password("pass"),
            attributes={"clearance_level": 3},
        )
        session.add(owner)
        session.flush()

        doc = Document(title="Gated Record", doc_type="record", created_by=owner.id)
        session.add(doc)
        session.flush()

        field = Field(
            document_id=doc.id,
            field_key="patient.diagnosis",
            field_type="text",
            requires_signoff=True,
            category=category,
        )
        session.add(field)
        session.flush()

        version = FieldVersion(
            field_id=field.id,
            value="Stage 2 Hypertension",
            value_hash=hash_value("Stage 2 Hypertension"),
            parent_version_id=[],
            created_by=owner.id,
            status="pending_signoff",
        )
        session.add(version)
        session.commit()
        return doc.id, field.id


def _get_token(api_client: TestClient, email: str, password: str) -> str:
    resp = api_client.post(f"{API}/auth/token", data={"username": email, "password": password})
    assert resp.status_code == 200
    return str(resp.json()["access_token"])


def test_clinician_can_signoff_phi_field(rbac_api_client: TestClient, engine: Engine) -> None:
    clinician_email, clinician_pass = _seed_user(engine, "clinician", 3, "cardiology")
    token = _get_token(rbac_api_client, clinician_email, clinician_pass)
    _, field_id = _create_gated_field(engine, "phi")

    resp = rbac_api_client.post(
        f"{API}/fields/{field_id}/signoff", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "active"


def test_compliance_officer_can_signoff_any_field(
    rbac_api_client: TestClient, engine: Engine
) -> None:
    officer_email, officer_pass = _seed_user(engine, "compliance_officer", 5, "compliance")
    token = _get_token(rbac_api_client, officer_email, officer_pass)
    _, field_id = _create_gated_field(engine, "phi")

    resp = rbac_api_client.post(
        f"{API}/fields/{field_id}/signoff", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "active"


def test_researcher_denied_signoff_on_phi_field(
    rbac_api_client: TestClient, engine: Engine
) -> None:
    researcher_email, researcher_pass = _seed_user(engine, "researcher", 2, "research")
    token = _get_token(rbac_api_client, researcher_email, researcher_pass)
    _, field_id = _create_gated_field(engine, "phi")

    resp = rbac_api_client.post(
        f"{API}/fields/{field_id}/signoff", headers={"Authorization": f"Bearer {token}"}
    )
    # Rejected with 403 Forbidden by the Gate
    assert resp.status_code == 403
    assert "denied" in resp.json()["detail"].lower()


def test_ai_agent_denied_signoff(rbac_api_client: TestClient, engine: Engine) -> None:
    agent_email, agent_pass = _seed_user(engine, "ai_agent", 2, "platform")
    token = _get_token(rbac_api_client, agent_email, agent_pass)
    _, field_id = _create_gated_field(engine, "clinical")

    resp = rbac_api_client.post(
        f"{API}/fields/{field_id}/signoff", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 403
