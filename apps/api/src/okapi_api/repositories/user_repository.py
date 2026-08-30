"""UserRepository — lookups for authentication (architecture doc section 10)."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from okapi_api.models import User


class UserRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, user_id: uuid.UUID) -> User | None:
        return self._session.get(User, user_id)

    def get_by_email(self, email: str) -> User | None:
        return self._session.scalars(select(User).where(User.email == email)).first()
