"""Integration tests fuzzing endpoints with adversarial payloads (Phase 09)."""

import uuid

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session
from starlette.testclient import TestClient

from okapi_api.core.security import hash_password
from okapi_api.models import User

pytestmark = pytest.mark.integration

API = "/api/v1"

FUZZ_PAYLOADS = [
    # SQL Injection attempts
    "' OR '1'='1",
    "'; DROP TABLE users; --",
    "UNION SELECT null, null, null--",
    # XSS payloads
    "<script>alert('xss')</script>",
    "<img src=x onerror=alert(1)>",
    # Path Traversal & Delimiters
    "../../../../etc/passwd",
    r"..\..\windows\system32",
    # Format string & Command injection
    "%s%s%s%s%s%s%s",
    "$(whoami)",
    "`id`",
    # Unicode bidi override & Null byte
    "normal_text\x00malicious",
    "patient\u202e\u202d[INJECTED]",
]


def _seed_fuzz_user(engine: Engine) -> tuple[str, str]:
    email = f"fuzz-{uuid.uuid4()}@okapi.dev"
    password = "pass"
    with Session(engine) as session:
        user = User(
            email=email,
            full_name="Fuzz Tester",
            role="clinician",
            password_hash=hash_password(password),
            attributes={"clearance_level": 3},
        )
        session.add(user)
        session.commit()
    return email, password


def test_fuzz_document_and_field_creation_with_malicious_inputs(
    api_client: TestClient, engine: Engine
) -> None:
    email, password = _seed_fuzz_user(engine)
    token = api_client.post(
        f"{API}/auth/token", data={"username": email, "password": password}
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    for payload in FUZZ_PAYLOADS:
        # Fuzz document creation
        doc_resp = api_client.post(
            f"{API}/documents",
            json={"title": f"Doc {payload}", "doc_type": "record"},
            headers=headers,
        )
        # Server must never crash (no 500)
        assert doc_resp.status_code in {201, 400, 422}

        if doc_resp.status_code == 201:
            doc_id = doc_resp.json()["id"]
            # Fuzz field creation
            field_resp = api_client.post(
                f"{API}/documents/{doc_id}/fields",
                json={
                    "field_key": f"test_{payload[:10].replace(' ', '_').replace('/', '_')}",
                    "value": payload,
                },
                headers=headers,
            )
            assert field_resp.status_code in {201, 400, 422}

            # Fuzz RAG query
            query_resp = api_client.post(
                f"{API}/documents/{doc_id}/query",
                json={"question": payload},
                headers=headers,
            )
            assert query_resp.status_code in {200, 400, 422}
