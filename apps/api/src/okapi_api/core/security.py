import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt

from okapi_api.core.config import get_settings


class TokenError(Exception):
    """Base exception for JWT processing errors."""


class TokenExpiredError(TokenError):
    """Raised when token's exp timestamp has passed."""


class TokenInvalidError(TokenError):
    """Raised when token signature, claims, or algorithm are invalid."""


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
        "jti": str(claims.get("jti") or uuid.uuid4()),
        "iat": now,
        "nbf": now,
        "exp": now + timedelta(seconds=settings.access_token_ttl_seconds),
        **claims,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        decoded: dict[str, Any] = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            options={
                "require": ["sub", "role", "actor_type", "exp", "iat", "jti"],
                "verify_signature": True,
                "verify_exp": True,
                "verify_nbf": True,
                "verify_iat": True,
            },
        )
        return decoded
    except jwt.ExpiredSignatureError as exc:
        raise TokenExpiredError("token has expired") from exc
    except jwt.ImmatureSignatureError as exc:
        raise TokenInvalidError("token is not yet valid (nbf)") from exc
    except jwt.InvalidAlgorithmError as exc:
        raise TokenInvalidError("unsupported or mismatched token algorithm") from exc
    except jwt.InvalidTokenError as exc:
        raise TokenInvalidError(f"invalid token: {exc}") from exc
