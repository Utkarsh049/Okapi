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
