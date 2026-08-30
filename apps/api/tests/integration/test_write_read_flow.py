"""End-to-end HTTP flow against a real Postgres (OPA stubbed to allow-all).

Exercises: token -> create document -> register field -> edit twice -> merge ->
lineage DAG -> integrity verify -> field-scoped read.
"""

import uuid

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from okapi_api.core.security import hash_password
from okapi_api.models import User

pytestmark = pytest.mark.integration

API = "/api/v1"


def _seed_clinician(engine: Engine) -> str:
    email = f"clinician-{uuid.uuid4()}@okapi.dev"
    with Session(engine) as session:
        session.add(
            User(
                email=email,
                full_name="Flow Tester",
                role="clinician",
                password_hash=hash_password("pw"),
                attributes={"clearance_level": 3, "department": "cardiology"},
            )
        )
        session.commit()
    return email


def test_full_write_and_read_flow(api_client, engine: Engine) -> None:  # type: ignore[no-untyped-def]
    email = _seed_clinician(engine)
    token = api_client.post(f"{API}/auth/token", data={"username": email, "password": "pw"}).json()[
        "access_token"
    ]
    headers = {"Authorization": f"Bearer {token}"}

    doc = api_client.post(
        f"{API}/documents",
        json={"title": "Rec", "doc_type": "patient_record"},
        headers=headers,
    ).json()

    field = api_client.post(
        f"{API}/documents/{doc['id']}/fields",
        json={
            "field_key": "patient.diagnosis",
            "category": "phi",
            "requires_signoff": True,
            "value": "v1",
        },
        headers=headers,
    ).json()

    v2 = api_client.patch(
        f"{API}/documents/{doc['id']}/fields/{field['id']}",
        json={"new_value": "v2"},
        headers=headers,
    ).json()
    assert v2["value_hash"] != field["id"]  # sanity: got a version back

    v3 = api_client.patch(
        f"{API}/documents/{doc['id']}/fields/{field['id']}",
        json={
            "new_value": "v3",
            "parent_version_ids": [v2["id"], v2["parent_version_id"][0]],
        },
        headers=headers,
    ).json()
    assert len(v3["parent_version_id"]) == 2  # merge node

    lineage = api_client.get(f"{API}/documents/{doc['id']}/lineage", headers=headers).json()
    assert len(lineage["nodes"]) == 3
    assert len(lineage["edges"]) >= 3

    integrity = api_client.get(f"{API}/documents/{doc['id']}/integrity", headers=headers).json()
    assert integrity["ok"] is True

    answer = api_client.post(
        f"{API}/documents/{doc['id']}/query",
        json={"question": "what is the diagnosis?"},
        headers=headers,
    ).json()
    assert "patient.diagnosis" in answer["allowed_fields"]

    audit = api_client.get(
        f"{API}/audit", params={"document_id": doc["id"]}, headers=headers
    ).json()
    assert len(audit) >= 1
