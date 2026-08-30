"""Authentication endpoint (architecture doc section 9).

``POST /auth/token`` issues a short-lived JWT whose claims (``sub``, ``role``,
``actor_type``, ``attributes``) are what the Gate's RBAC/ABAC policies key off.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from okapi_api.core.deps import get_user_repo
from okapi_api.core.security import encode_access_token, verify_password
from okapi_api.repositories.user_repository import UserRepository

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/token")
def issue_token(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    users: Annotated[UserRepository, Depends(get_user_repo)],
) -> dict[str, str]:
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
