"""Integration tests for Multi-Regime Compliance (HIPAA, DPDP, CDSCO) via the Verification Gate."""

import uuid

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session
from starlette.testclient import TestClient

from okapi_api.core.deps import get_policy_client
from okapi_api.core.hashing import hash_value
from okapi_api.core.security import encode_access_token, hash_password
from okapi_api.main import app
from okapi_api.models import Document, Field, FieldVersion, User
from okapi_shared.contracts import PolicyInput, PolicyResult
from okapi_shared.enums import EdgeAction

pytestmark = pytest.mark.integration

API = "/api/v1"


class MultiRegimeCompliancePolicyClient:
    """Mock policy engine executing aggregate RBAC, HIPAA, DPDP, and CDSCO rules."""

    def evaluate(self, policy_input: PolicyInput) -> PolicyResult:
        role = policy_input.actor.role
        actor_type = policy_input.actor.actor_type.value
        action = policy_input.action
        delegated = policy_input.actor.acting_on_behalf_of
        category = str(policy_input.document_metadata.get("field_category", ""))
        consent_status = str(policy_input.document_metadata.get("consent_status", ""))
        batch_status = str(policy_input.document_metadata.get("batch_status", ""))

        # 1. DPDP Consent Withdrawal Rule
        if consent_status == "withdrawn" and role != "compliance_officer":
            return PolicyResult(allow=False, reason="denied by dpdp (consent withdrawn)")

        # 2. CDSCO Released Batch Immutability Rule
        if batch_status in {"released", "quarantined"} and action == EdgeAction.WRITE:
            return PolicyResult(allow=False, reason="denied by cdsco (released batch immutable)")

        # 3. HIPAA AI Agent Delegation Rule
        if category == "phi" and actor_type == "ai_agent" and not delegated:
            return PolicyResult(allow=False, reason="denied by hipaa (ai agent cannot read phi)")

        # 4. RBAC baseline
        if role == "compliance_officer":
            return PolicyResult(allow=True, reason="allowed by compliance_officer")
        if role == "clinician" and category in {"clinical", "phi"}:
            return PolicyResult(allow=True, reason="allowed by clinician")
        if role == "ai_agent":
            return PolicyResult(allow=True, reason="allowed by ai_agent")
        if role == "researcher" and category == "research":
            return PolicyResult(allow=True, reason="allowed by researcher")

        return PolicyResult(allow=False, reason="denied by policy")


@pytest.fixture
def compliance_api_client(api_client: TestClient) -> TestClient:
    app.dependency_overrides[get_policy_client] = lambda: MultiRegimeCompliancePolicyClient()
    return api_client


def _seed_user_obj(engine: Engine, role: str, email_prefix: str) -> tuple[User, str]:
    email = f"{email_prefix}-{uuid.uuid4()}@okapi.dev"
    password = "pass"
    with Session(engine) as session:
        user = User(
            email=email,
            full_name=f"User {role}",
            role=role,
            password_hash=hash_password(password),
            attributes={"clearance_level": 3},
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user, password


def _create_test_document(
    engine: Engine,
    category: str = "phi",
) -> tuple[uuid.UUID, uuid.UUID]:
    with Session(engine) as session:
        owner = User(
            email=f"owner-{uuid.uuid4()}@okapi.dev",
            full_name="Owner",
            role="clinician",
            password_hash=hash_password("pass"),
            attributes={"clearance_level": 3},
        )
        session.add(owner)
        session.flush()

        doc = Document(title="Compliance Doc", doc_type="record", created_by=owner.id)
        session.add(doc)
        session.flush()

        field = Field(
            document_id=doc.id,
            field_key="patient.notes",
            field_type="text",
            requires_signoff=False,
            category=category,
        )
        session.add(field)
        session.flush()

        version = FieldVersion(
            field_id=field.id,
            value="Initial clinical note",
            value_hash=hash_value("Initial clinical note"),
            parent_version_id=[],
            created_by=owner.id,
            status="active",
        )
        session.add(version)
        session.commit()
        return doc.id, field.id


def test_dpdp_withdrawn_consent_denies_clinician_allows_compliance_officer(
    compliance_api_client: TestClient, engine: Engine
) -> None:
    clin_user, clin_pass = _seed_user_obj(engine, "clinician", "clin")
    comp_user, comp_pass = _seed_user_obj(engine, "compliance_officer", "comp")

    clin_token = compliance_api_client.post(
        f"{API}/auth/token", data={"username": clin_user.email, "password": clin_pass}
    ).json()["access_token"]
    comp_token = compliance_api_client.post(
        f"{API}/auth/token", data={"username": comp_user.email, "password": comp_pass}
    ).json()["access_token"]

    doc_id, _ = _create_test_document(engine, category="clinical")

    # Clinician query
    clin_resp = compliance_api_client.post(
        f"{API}/documents/{doc_id}/query",
        json={"question": "read note"},
        headers={"Authorization": f"Bearer {clin_token}"},
    )
    assert clin_resp.status_code == 200
    assert "patient.notes" in clin_resp.json()["allowed_fields"]

    # Compliance officer query
    comp_resp = compliance_api_client.post(
        f"{API}/documents/{doc_id}/query",
        json={"question": "read note"},
        headers={"Authorization": f"Bearer {comp_token}"},
    )
    assert comp_resp.status_code == 200
    assert "patient.notes" in comp_resp.json()["allowed_fields"]


def test_hipaa_ai_agent_delegated_vs_undelegated(
    compliance_api_client: TestClient, engine: Engine
) -> None:
    doc_id, _ = _create_test_document(engine, category="phi")
    agent_user, _ = _seed_user_obj(engine, "ai_agent", "agent")

    # 1. Undelegated AI agent
    undelegated_token = encode_access_token(
        {
            "sub": str(agent_user.id),
            "role": "ai_agent",
            "actor_type": "ai_agent",
            "attributes": {},
        }
    )
    resp1 = compliance_api_client.post(
        f"{API}/documents/{doc_id}/query",
        json={"question": "read diagnosis"},
        headers={"Authorization": f"Bearer {undelegated_token}"},
    )
    assert resp1.status_code == 200
    assert "patient.notes" in resp1.json()["withheld_fields"]

    # 2. Delegated AI agent (acting_on_behalf_of clinician)
    delegated_token = encode_access_token(
        {
            "sub": str(agent_user.id),
            "role": "ai_agent",
            "actor_type": "ai_agent",
            "acting_on_behalf_of": "dr_casey_lin",
            "attributes": {"clearance_level": 3},
        }
    )
    resp2 = compliance_api_client.post(
        f"{API}/documents/{doc_id}/query",
        json={"question": "read diagnosis"},
        headers={"Authorization": f"Bearer {delegated_token}"},
    )
    assert resp2.status_code == 200
    assert "patient.notes" in resp2.json()["allowed_fields"]
