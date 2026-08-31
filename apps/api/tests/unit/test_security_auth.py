"""Unit tests for hardened AuthN security primitives, JWT claims, and token revocation."""

import time
import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from okapi_api.core.config import get_settings
from okapi_api.core.security import (
    TokenExpiredError,
    TokenInvalidError,
    decode_access_token,
    encode_access_token,
    hash_password,
    verify_password,
)
from okapi_api.core.token_store import InMemoryTokenRevocationStore


def test_password_hash_and_verification() -> None:
    hashed = hash_password("super-secure-pass")
    assert verify_password("super-secure-pass", hashed) is True
    assert verify_password("wrong-pass", hashed) is False


def test_encode_and_decode_access_token_roundtrip() -> None:
    user_id = str(uuid.uuid4())
    token = encode_access_token(
        {
            "sub": user_id,
            "role": "clinician",
            "actor_type": "human",
            "attributes": {"clearance_level": 3},
        }
    )
    claims = decode_access_token(token)
    assert claims["sub"] == user_id
    assert claims["role"] == "clinician"
    assert claims["actor_type"] == "human"
    assert "jti" in claims
    assert "nbf" in claims
    assert "iat" in claims
    assert "exp" in claims


def test_expired_token_raises_token_expired_error() -> None:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(uuid.uuid4()),
        "role": "researcher",
        "actor_type": "human",
        "jti": str(uuid.uuid4()),
        "iat": now - timedelta(seconds=200),
        "nbf": now - timedelta(seconds=200),
        "exp": now - timedelta(seconds=100),  # expired
    }
    expired_token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    with pytest.raises(TokenExpiredError):
        decode_access_token(expired_token)


def test_token_with_future_nbf_fails() -> None:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(uuid.uuid4()),
        "role": "researcher",
        "actor_type": "human",
        "jti": str(uuid.uuid4()),
        "iat": now,
        "nbf": now + timedelta(seconds=300),  # future
        "exp": now + timedelta(seconds=600),
    }
    future_token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    with pytest.raises(TokenInvalidError):
        decode_access_token(future_token)


def test_algorithm_confusion_attack_rejected() -> None:
    now = datetime.now(UTC)
    payload = {
        "sub": str(uuid.uuid4()),
        "role": "admin",
        "actor_type": "human",
        "jti": str(uuid.uuid4()),
        "iat": now,
        "nbf": now,
        "exp": now + timedelta(seconds=300),
    }
    # Unsigned token with alg: none
    none_token = jwt.encode(payload, key="", algorithm="none")
    with pytest.raises(TokenInvalidError):
        decode_access_token(none_token)


def test_missing_required_claims_rejected() -> None:
    settings = get_settings()
    now = datetime.now(UTC)
    # Missing 'jti' and 'actor_type'
    payload = {
        "sub": str(uuid.uuid4()),
        "role": "clinician",
        "iat": now,
        "nbf": now,
        "exp": now + timedelta(seconds=300),
    }
    invalid_token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    with pytest.raises(TokenInvalidError):
        decode_access_token(invalid_token)


def test_token_revocation_store_lifecycle() -> None:
    store = InMemoryTokenRevocationStore()
    jti = str(uuid.uuid4())
    assert store.is_revoked(jti) is False

    # Revoke token valid for 5 seconds
    store.revoke(jti, time.time() + 5)
    assert store.is_revoked(jti) is True

    # Check already expired revocation eviction
    old_jti = str(uuid.uuid4())
    store.revoke(old_jti, time.time() - 10)  # already expired
    assert store.is_revoked(old_jti) is False
