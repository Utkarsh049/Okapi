"""Authentication and token lifecycle endpoints (architecture doc section 9).

``POST /auth/token`` issues a short-lived, claim-validated JWT.
``POST /auth/revoke`` blacklists the active JWT ID (jti) in the token revocation store.
"""

import threading
import time
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm

from okapi_api.core.deps import (
    CurrentActor,
    get_token_store,
    get_user_repo,
    oauth2_scheme,
)
from okapi_api.core.security import decode_access_token, encode_access_token, verify_password
from okapi_api.core.token_store import TokenRevocationStore
from okapi_api.repositories.user_repository import UserRepository

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginAttemptTracker:
    """In-memory rate limiter to mitigate brute-force and credential stuffing attacks."""

    def __init__(self, max_attempts: int = 5, window_seconds: int = 60) -> None:
        self._lock = threading.Lock()
        self._attempts: dict[str, list[float]] = {}
        self._max_attempts = max_attempts
        self._window_seconds = window_seconds

    def check(self, key: str) -> None:
        now = time.time()
        with self._lock:
            timestamps = [t for t in self._attempts.get(key, []) if now - t < self._window_seconds]
            if len(timestamps) >= self._max_attempts:
                raise HTTPException(
                    status.HTTP_429_TOO_MANY_REQUESTS,
                    "Too many failed login attempts. Please wait before retrying.",
                )
            self._attempts[key] = timestamps

    def record_failure(self, key: str) -> None:
        now = time.time()
        with self._lock:
            timestamps = [t for t in self._attempts.get(key, []) if now - t < self._window_seconds]
            timestamps.append(now)
            self._attempts[key] = timestamps

    def clear(self, key: str) -> None:
        with self._lock:
            self._attempts.pop(key, None)


_login_tracker = LoginAttemptTracker()


@router.post("/token")
def issue_token(
    request: Request,
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    users: Annotated[UserRepository, Depends(get_user_repo)],
) -> dict[str, str]:
    # Key rate limiting by client IP and username
    client_ip = request.client.host if request.client else "unknown"
    rate_key = f"{client_ip}:{form.username.lower()}"
    _login_tracker.check(rate_key)

    user = users.get_by_email(form.username)
    if user is None or not verify_password(form.password, user.password_hash):
        _login_tracker.record_failure(rate_key)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "incorrect email or password")

    _login_tracker.clear(rate_key)
    token = encode_access_token(
        {
            "sub": str(user.id),
            "role": user.role,
            "actor_type": user.actor_type.value,
            "attributes": user.attributes,
        }
    )
    return {"access_token": token, "token_type": "bearer"}


@router.post("/revoke")
def revoke_token(
    actor: CurrentActor,
    token: Annotated[str, Depends(oauth2_scheme)],
    token_store: Annotated[TokenRevocationStore, Depends(get_token_store)],
) -> dict[str, str]:
    """Revoke the current access token (logout)."""
    claims = decode_access_token(token)
    jti = claims.get("jti")
    exp = claims.get("exp")
    if not jti or not exp:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "token cannot be revoked (missing jti/exp)"
        )

    token_store.revoke(str(jti), float(exp))
    return {"status": "revoked", "jti": str(jti)}
