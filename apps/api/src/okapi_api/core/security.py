"""JWT encode/decode and password hashing (architecture doc section 6).

AuthZ is delegated to OPA; this module only handles AuthN primitives.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt

from okapi_api.core.config import get_settings


def hash_password(plain: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(plain.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


def encode_access_token(claims: dict[str, Any]) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        **claims,
        "iat": now,
        "exp": now + timedelta(seconds=settings.access_token_ttl_seconds),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    decoded: dict[str, Any] = jwt.decode(
        token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
    )
    return decoded
