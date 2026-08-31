"""Adversarial tests for JWT privilege escalation and token tampering (Phase 10)."""

import base64
import json
import time
import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from starlette.testclient import TestClient

from okapi_api.core.config import get_settings
from okapi_api.core.security import encode_access_token

pytestmark = pytest.mark.integration

API = "/api/v1"


def test_forged_jwt_secret_rejected(api_client: TestClient) -> None:
    forged_token = jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "role": "admin",
            "jti": str(uuid.uuid4()),
            "exp": datetime.now(UTC) + timedelta(minutes=15),
            "iat": datetime.now(UTC),
            "nbf": datetime.now(UTC),
        },
        "wrong-secret-key-attacker-guess-32b",
        algorithm="HS256",
    )
    resp = api_client.post(
        f"{API}/documents",
        json={"title": "Test", "doc_type": "record"},
        headers={"Authorization": f"Bearer {forged_token}"},
    )
    assert resp.status_code == 401


def test_forged_claims_tampered_payload_rejected(api_client: TestClient) -> None:
    # Create legitimate token
    user_id = str(uuid.uuid4())
    token = encode_access_token(
        {
            "sub": user_id,
            "role": "researcher",
            "attributes": {"clearance_level": 1},
        }
    )

    # Split JWT and modify the payload part (escalate role and clearance)
    parts = token.split(".")
    assert len(parts) == 3

    # Tampered payload
    tampered_payload = jwt.decode(token, options={"verify_signature": False})
    tampered_payload["role"] = "clinician"
    tampered_payload["attributes"] = {"clearance_level": 3}

    tampered_bytes = (
        base64.urlsafe_b64encode(json.dumps(tampered_payload).encode()).rstrip(b"=").decode()
    )
    tampered_token = f"{parts[0]}.{tampered_bytes}.{parts[2]}"

    resp = api_client.post(
        f"{API}/documents",
        json={"title": "Test", "doc_type": "record"},
        headers={"Authorization": f"Bearer {tampered_token}"},
    )
    assert resp.status_code == 401


def test_none_algorithm_jwt_rejected(api_client: TestClient) -> None:
    # Attempt "none" algorithm attack
    header = {"alg": "none", "typ": "JWT"}
    payload = {
        "sub": str(uuid.uuid4()),
        "role": "admin",
        "jti": str(uuid.uuid4()),
        "exp": int(time.time()) + 3600,
    }
    none_token = jwt.encode(payload, key="", algorithm="none", headers=header)

    resp = api_client.post(
        f"{API}/documents",
        json={"title": "Test", "doc_type": "record"},
        headers={"Authorization": f"Bearer {none_token}"},
    )
    assert resp.status_code == 401


def test_expired_token_rejected(api_client: TestClient) -> None:
    settings = get_settings()
    expired_token = jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "role": "clinician",
            "jti": str(uuid.uuid4()),
            "exp": datetime.now(UTC) - timedelta(minutes=5),
            "iat": datetime.now(UTC) - timedelta(minutes=20),
            "nbf": datetime.now(UTC) - timedelta(minutes=20),
        },
        settings.jwt_secret,
        algorithm="HS256",
    )
    resp = api_client.post(
        f"{API}/documents",
        json={"title": "Test", "doc_type": "record"},
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert resp.status_code == 401


def test_not_yet_valid_nbf_token_rejected(api_client: TestClient) -> None:
    settings = get_settings()
    future_token = jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "role": "clinician",
            "jti": str(uuid.uuid4()),
            "exp": datetime.now(UTC) + timedelta(hours=1),
            "iat": datetime.now(UTC),
            "nbf": datetime.now(UTC) + timedelta(minutes=10),
        },
        settings.jwt_secret,
        algorithm="HS256",
    )
    resp = api_client.post(
        f"{API}/documents",
        json={"title": "Test", "doc_type": "record"},
        headers={"Authorization": f"Bearer {future_token}"},
    )
    assert resp.status_code == 401
