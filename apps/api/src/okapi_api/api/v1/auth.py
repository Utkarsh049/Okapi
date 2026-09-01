"""Authentication and token lifecycle endpoints (architecture doc section 9).

``POST /auth/token`` issues a short-lived, claim-validated JWT.
``POST /auth/revoke`` blacklists the active JWT ID (jti) in the token revocation store.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm

from okapi_api.core.deps import (
    CurrentActor,
    get_token_store,
    get_user_repo,
    oauth2_scheme,
)
from okapi_api.core.rate_limit import get_global_rate_limiter
from okapi_api.core.security import decode_access_token, encode_access_token, verify_password
from okapi_api.core.token_store import TokenRevocationStore
from okapi_api.repositories.user_repository import UserRepository

router = APIRouter(prefix="/auth", tags=["auth"])

_LOGIN_MAX_ATTEMPTS = 5
_LOGIN_WINDOW_SECONDS = 60.0


@router.post("/token")
def issue_token(
    request: Request,
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    users: Annotated[UserRepository, Depends(get_user_repo)],
) -> dict[str, str]:
    # Key rate limiting by client IP and username; counts every attempt (not just
    # failures) so a string of failures followed by one success can't reset the
    # window and keep a credential-stuffing run going indefinitely.
    client_ip = request.client.host if request.client else "unknown"
    rate_key = f"login:{client_ip}:{form.username.lower()}"
    allowed, retry_after = get_global_rate_limiter().check_rate_limit(
        rate_key, max_requests=_LOGIN_MAX_ATTEMPTS, window_seconds=_LOGIN_WINDOW_SECONDS
    )
    if not allowed:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many failed login attempts. Please wait before retrying.",
            headers={"Retry-After": str(retry_after)},
        )

    user = users.get_by_email(form.username)
    if user is None or not verify_password(form.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "incorrect email or password")

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
