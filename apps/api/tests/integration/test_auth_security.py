"""Integration tests for token revocation flow and auth endpoint security."""

import uuid

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session
from starlette.testclient import TestClient

from okapi_api.core.security import hash_password
from okapi_api.models import User

pytestmark = pytest.mark.integration

API = "/api/v1"


def _seed_test_user(engine: Engine) -> tuple[str, str]:
    email = f"sec-test-{uuid.uuid4()}@okapi.dev"
    password = "correct-password-123"
    with Session(engine) as session:
        session.add(
            User(
                email=email,
                full_name="Security Test User",
                role="clinician",
                password_hash=hash_password(password),
                attributes={"clearance_level": 3, "department": "security"},
            )
        )
        session.commit()
    return email, password


def test_token_revoke_lifecycle_integration(api_client: TestClient, engine: Engine) -> None:
    email, password = _seed_test_user(engine)

    # 1. Login and obtain token
    login_resp = api_client.post(
        f"{API}/auth/token", data={"username": email, "password": password}
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Access authenticated endpoint
    doc_resp = api_client.post(
        f"{API}/documents", json={"title": "Sec Doc", "doc_type": "record"}, headers=headers
    )
    assert doc_resp.status_code == 201

    # 3. Revoke active token
    revoke_resp = api_client.post(f"{API}/auth/revoke", headers=headers)
    assert revoke_resp.status_code == 200
    assert revoke_resp.json()["status"] == "revoked"

    # 4. Attempt to reuse revoked token -> 401 Unauthorized
    reused_resp = api_client.post(
        f"{API}/documents", json={"title": "Sec Doc 2", "doc_type": "record"}, headers=headers
    )
    assert reused_resp.status_code == 401
    assert "revoked" in reused_resp.json()["detail"]


def test_login_brute_force_throttling(api_client: TestClient, engine: Engine) -> None:
    email, _ = _seed_test_user(engine)

    # Trigger 5 consecutive failed attempts
    for _ in range(5):
        resp = api_client.post(
            f"{API}/auth/token", data={"username": email, "password": "wrong-password"}
        )
        assert resp.status_code == 401

    # 6th attempt should be rate limited with 429
    throttled_resp = api_client.post(
        f"{API}/auth/token", data={"username": email, "password": "wrong-password"}
    )
    assert throttled_resp.status_code == 429
    assert "Too many failed login attempts" in throttled_resp.json()["detail"]
