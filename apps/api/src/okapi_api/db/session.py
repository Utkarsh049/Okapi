"""SQLAlchemy engine + session factory — the only place a ``Session`` is created.

Synchronous by design (architecture doc prototype scale): FastAPI runs sync routes in
a threadpool, Alembic drives migrations directly, and repositories/tests stay simple.
"""

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from okapi_api.core.config import get_settings

_engine = create_engine(get_settings().database_url, future=True, pool_pre_ping=True)
SessionFactory = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False)


def get_session() -> Iterator[Session]:
    """FastAPI dependency: yield a session, roll back on error, always close."""
    session = SessionFactory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
