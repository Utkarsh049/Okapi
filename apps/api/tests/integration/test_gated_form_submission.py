"""Integration test verifying end-to-end AI Form Autofill and Human Sign-Off Barrier (Phase 07)."""

import uuid

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session
from starlette.testclient import TestClient

from okapi_api.core.security import hash_password
from okapi_api.models import Document, User
from okapi_api.repositories.field_repository import FieldRepository
from okapi_api.services.versioning_service import VersioningService

pytestmark = pytest.mark.integration

API = "/api/v1"


def _seed_users(engine: Engine) -> dict[str, tuple[str, str]]:
    clinician_email = f"clinician-{uuid.uuid4()}@okapi.dev"
    agent_email = f"agent-{uuid.uuid4()}@okapi.dev"
    password = "pass"

    with Session(engine) as session:
        clinician = User(
            email=clinician_email,
            full_name="Dr. Signoff Approver",
            role="clinician",
            password_hash=hash_password(password),
            attributes={"clearance_level": 3, "department": "cardiology"},
        )
        agent = User(
            email=agent_email,
            full_name="Autonomous Form Agent",
            role="ai_agent",
            password_hash=hash_password(password),
            attributes={"clearance_level": 2},
        )
        session.add_all([clinician, agent])
        session.commit()

    return {
        "clinician": (clinician_email, password),
        "agent": (agent_email, password),
    }


def _seed_source_and_target_forms(
    engine: Engine,
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID]:
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

        # 1. Source Document with patient data
        src_doc = Document(title="Source Patient Record", doc_type="record", created_by=owner.id)
        session.add(src_doc)
        session.flush()

        field_repo = FieldRepository(session)
        version_service = VersioningService(field_repo)

        f_diag = field_repo.register_field(
            document_id=src_doc.id, field_key="patient.diagnosis", category="phi"
        )
        version_service.create_version(
            field_id=f_diag.id, new_value="Essential Hypertension", actor_id=owner.id
        )

        f_bp = field_repo.register_field(
            document_id=src_doc.id, field_key="vitals.blood_pressure", category="clinical"
        )
        version_service.create_version(field_id=f_bp.id, new_value="140/90", actor_id=owner.id)

        # 2. Target Form Document with required fields
        form_doc = Document(title="Discharge Form", doc_type="form", created_by=owner.id)
        session.add(form_doc)
        session.flush()

        target_diag = field_repo.register_field(
            document_id=form_doc.id,
            field_key="patient.diagnosis",
            requires_signoff=True,
            category="phi",
        )
        target_bp = field_repo.register_field(
            document_id=form_doc.id,
            field_key="vitals.blood_pressure",
            requires_signoff=False,
            category="clinical",
        )
        session.commit()
        return src_doc.id, form_doc.id, target_diag.id, target_bp.id


def test_gated_form_autofill_and_submission_workflow(
    api_client: TestClient, engine: Engine
) -> None:
    users = _seed_users(engine)
    agent_email, agent_pass = users["agent"]
    clin_email, clin_pass = users["clinician"]

    agent_token = api_client.post(
        f"{API}/auth/token", data={"username": agent_email, "password": agent_pass}
    ).json()["access_token"]
    clin_token = api_client.post(
        f"{API}/auth/token", data={"username": clin_email, "password": clin_pass}
    ).json()["access_token"]

    src_id, form_id, target_diag_id, target_bp_id = _seed_source_and_target_forms(engine)

    # Step 1: AI Agent autofills the form from the source record
    autofill_resp = api_client.post(
        f"{API}/forms/{form_id}/autofill",
        json={"source_document_ids": [str(src_id)]},
        headers={"Authorization": f"Bearer {agent_token}"},
    )
    assert autofill_resp.status_code == 200
    autofill_data = autofill_resp.json()
    assert autofill_data["pending_signoff_count"] == 1
    assert len(autofill_data["drafted_fields"]) == 2

    # Step 2: Attempt submission before human sign-off -> MUST FAIL WITH 422!
    submit_fail_resp = api_client.post(
        f"{API}/forms/{form_id}/submit",
        headers={"Authorization": f"Bearer {agent_token}"},
    )
    assert submit_fail_resp.status_code == 422
    fail_data = submit_fail_resp.json()
    assert "blocked" in fail_data["detail"]["message"].lower()

    # Step 3: Human Clinician signs off on the diagnosis field
    signoff_resp = api_client.post(
        f"{API}/fields/{target_diag_id}/signoff",
        json={"reason": "Verified clinical accuracy of diagnosis"},
        headers={"Authorization": f"Bearer {clin_token}"},
    )
    assert signoff_resp.status_code == 200

    # Step 4: Submit form again -> MUST SUCCEED (200 OK)!
    submit_success_resp = api_client.post(
        f"{API}/forms/{form_id}/submit",
        headers={"Authorization": f"Bearer {clin_token}"},
    )
    assert submit_success_resp.status_code == 200
    success_data = submit_success_resp.json()
    assert success_data["status"] == "submitted"
    assert "patient.diagnosis" in success_data["signed_off_fields"]
    assert "vitals.blood_pressure" in success_data["signed_off_fields"]
