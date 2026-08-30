"""Integration tests for the document extraction endpoint (Phase 04)."""

import uuid

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session
from starlette.testclient import TestClient

from okapi_api.core.security import hash_password
from okapi_api.models import Document, User

pytestmark = pytest.mark.integration

API = "/api/v1"


def _seed_test_clinician(engine: Engine) -> tuple[str, str]:
    email = f"clinician-{uuid.uuid4()}@okapi.dev"
    password = "pass"
    with Session(engine) as session:
        user = User(
            email=email,
            full_name="Dr. Extractor",
            role="clinician",
            password_hash=hash_password(password),
            attributes={"clearance_level": 3, "department": "cardiology"},
        )
        session.add(user)
        session.commit()
    return email, password


def _create_document(engine: Engine) -> uuid.UUID:
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

        doc = Document(title="Extraction Target", doc_type="record", created_by=owner.id)
        session.add(doc)
        session.commit()
        return doc.id


def test_extract_endpoint_without_auto_register(api_client: TestClient, engine: Engine) -> None:
    email, password = _seed_test_clinician(engine)
    token = api_client.post(
        f"{API}/auth/token", data={"username": email, "password": password}
    ).json()["access_token"]
    doc_id = _create_document(engine)

    note = "Clinical Impression: Stage 2 Hypertension. Plan: Metoprolol 50mg daily."
    resp = api_client.post(
        f"{API}/documents/{doc_id}/extract",
        json={"raw_text": note, "auto_register": False},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["document_id"] == str(doc_id)
    assert len(data["extracted_fields"]) >= 1
    assert data["registered_field_ids"] == []


def test_extract_endpoint_with_auto_register(api_client: TestClient, engine: Engine) -> None:
    email, password = _seed_test_clinician(engine)
    token = api_client.post(
        f"{API}/auth/token", data={"username": email, "password": password}
    ).json()["access_token"]
    doc_id = _create_document(engine)

    note = "Assessment: Acute Bronchitis. Vitals: BP 120/80. Plan: Azithromycin."
    resp = api_client.post(
        f"{API}/documents/{doc_id}/extract",
        json={"raw_text": note, "auto_register": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["document_id"] == str(doc_id)
    assert len(data["registered_field_ids"]) >= 1
