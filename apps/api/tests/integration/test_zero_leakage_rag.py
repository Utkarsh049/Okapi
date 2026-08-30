"""Integration tests verifying zero-leakage field boundaries in semantic RAG (Phase 06)."""

import uuid

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session
from starlette.testclient import TestClient

from okapi_api.core.deps import get_policy_client
from okapi_api.core.security import hash_password
from okapi_api.main import app
from okapi_api.models import Document, User
from okapi_api.repositories.field_repository import FieldRepository
from okapi_api.services.versioning_service import VersioningService
from okapi_shared.contracts import PolicyInput, PolicyResult

pytestmark = pytest.mark.integration

API = "/api/v1"


class GatedRagPolicyClient:
    def evaluate(self, policy_input: PolicyInput) -> PolicyResult:
        role = policy_input.actor.role
        category = str(policy_input.document_metadata.get("field_category", ""))
        if role == "researcher" and category != "research":
            return PolicyResult(allow=False, reason="researcher restricted to research category")
        if role == "clinician":
            return PolicyResult(allow=True, reason="clinician allowed")
        if role == "researcher" and category == "research":
            return PolicyResult(allow=True, reason="researcher allowed for research")
        return PolicyResult(allow=False, reason="denied by policy")


@pytest.fixture
def rag_api_client(api_client: TestClient) -> TestClient:
    app.dependency_overrides[get_policy_client] = lambda: GatedRagPolicyClient()
    return api_client


def _seed_test_users(engine: Engine) -> dict[str, tuple[str, str]]:
    clinician_email = f"clinician-{uuid.uuid4()}@okapi.dev"
    researcher_email = f"researcher-{uuid.uuid4()}@okapi.dev"
    password = "pass"

    with Session(engine) as session:
        clinician = User(
            email=clinician_email,
            full_name="Dr. Cardio",
            role="clinician",
            password_hash=hash_password(password),
            attributes={"clearance_level": 3, "department": "cardiology"},
        )
        researcher = User(
            email=researcher_email,
            full_name="Dr. Research",
            role="researcher",
            password_hash=hash_password(password),
            attributes={"clearance_level": 1, "department": "epidemiology"},
        )
        session.add_all([clinician, researcher])
        session.commit()

    return {
        "clinician": (clinician_email, password),
        "researcher": (researcher_email, password),
    }


def _seed_cardiology_document(engine: Engine) -> uuid.UUID:
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

        doc = Document(title="Cardiology RAG Test", doc_type="record", created_by=owner.id)
        session.add(doc)
        session.flush()

        field_repo = FieldRepository(session)
        version_service = VersioningService(field_repo)

        # 1. PHI Field (high vector relevance to query)
        f_phi = field_repo.register_field(
            document_id=doc.id, field_key="patient.diagnosis", category="phi"
        )
        version_service.create_version(
            field_id=f_phi.id,
            new_value="Severe Acute Myocardial Infarction with elevated troponin",
            actor_id=owner.id,
        )

        # 2. Research Field (low relevance to heart attack, but permitted to researcher)
        f_res = field_repo.register_field(
            document_id=doc.id, field_key="study.cohort_size", category="research"
        )
        version_service.create_version(
            field_id=f_res.id,
            new_value="Cohort 250 patients enrolled in trial",
            actor_id=owner.id,
        )
        session.commit()
        return doc.id


def test_zero_leakage_researcher_blocked_from_high_similarity_phi(
    rag_api_client: TestClient, engine: Engine
) -> None:
    users = _seed_test_users(engine)
    res_email, res_pass = users["researcher"]
    token = rag_api_client.post(
        f"{API}/auth/token", data={"username": res_email, "password": res_pass}
    ).json()["access_token"]
    doc_id = _seed_cardiology_document(engine)

    # Query directly targeting the PHI field
    query_body = {"question": "What is the acute myocardial infarction diagnosis?"}
    resp = rag_api_client.post(
        f"{API}/documents/{doc_id}/query",
        json=query_body,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()

    # Researcher only receives study.cohort_size
    assert "study.cohort_size" in data["allowed_fields"]
    assert "patient.diagnosis" in data["withheld_fields"]
    assert "patient.diagnosis" not in data["fields"]

    # Critical Zero-Leakage Assertion: PHI text must NOT appear in the answer!
    assert "Myocardial Infarction" not in data["answer"]
    assert "troponin" not in data["answer"]


def test_clinician_can_query_permitted_phi(rag_api_client: TestClient, engine: Engine) -> None:
    users = _seed_test_users(engine)
    clin_email, clin_pass = users["clinician"]
    token = rag_api_client.post(
        f"{API}/auth/token", data={"username": clin_email, "password": clin_pass}
    ).json()["access_token"]
    doc_id = _seed_cardiology_document(engine)

    query_body = {"question": "What is the diagnosis?"}
    resp = rag_api_client.post(
        f"{API}/documents/{doc_id}/query",
        json=query_body,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()

    assert "patient.diagnosis" in data["allowed_fields"]
    assert "patient.diagnosis" in data["fields"]
    assert "Myocardial Infarction" in data["fields"]["patient.diagnosis"]
