"""Shared test fixtures.

Unit tests need nothing here. Integration tests use ``db_session``, which requires a
live Postgres (the ``infra/docker-compose.test.yml`` instance on :55432, or set
``OKAPI_TEST_DATABASE_URL``). When no database is reachable those tests skip rather
than fail.
"""

import os
from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from okapi_api.models import Base

TEST_DB_URL = os.environ.get(
    "OKAPI_TEST_DATABASE_URL",
    "postgresql+psycopg://okapi:okapi@localhost:55432/okapi_test",
)


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    eng = create_engine(TEST_DB_URL, future=True, connect_args={"connect_timeout": 2})
    try:
        with eng.connect() as conn:
            conn.exec_driver_sql("SELECT 1")
    except Exception as exc:  # noqa: BLE001 - any conn(auth, refused, missing db) -> skip
        pytest.skip(f"no test database at {TEST_DB_URL}: {exc}", allow_module_level=True)
    Base.metadata.drop_all(eng)
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def db_session(engine: Engine) -> Iterator[Session]:
    connection = engine.connect()
    trans = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        trans.rollback()
        connection.close()


@pytest.fixture
def api_client(engine: Engine) -> Iterator[object]:
    """TestClient wired to the test engine, with OPA stubbed to allow-all.

    Auth stays real (token issue + JWT decode); only the policy client is swapped so
    the write/read *mechanism* can be exercised without a running OPA.
    """
    from fastapi.testclient import TestClient
    from sqlalchemy.orm import sessionmaker

    from okapi_api.core.deps import get_policy_client
    from okapi_api.db.session import get_session
    from okapi_api.gate.policy_client import StubPolicyClient
    from okapi_api.main import app

    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def _session_override() -> Iterator[Session]:
        session = factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    app.dependency_overrides[get_session] = _session_override
    app.dependency_overrides[get_policy_client] = lambda: StubPolicyClient()
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
