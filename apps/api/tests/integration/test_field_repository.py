"""FieldRepository against a real Postgres: version chains, merges, and the CTE."""

import uuid

import pytest
from sqlalchemy.orm import Session

from okapi_api.core.hashing import hash_value
from okapi_api.models import Document, Field, User
from okapi_api.repositories.field_repository import FieldRepository

pytestmark = pytest.mark.integration


def _bootstrap(session: Session) -> tuple[Field, uuid.UUID]:
    user = User(
        email=f"chain-{uuid.uuid4()}@okapi.dev",
        full_name="Chain Tester",
        role="clinician",
        password_hash="x",
        attributes={},
    )
    session.add(user)
    session.flush()
    doc = Document(title="t", doc_type="d", created_by=user.id)
    session.add(doc)
    session.flush()
    field = FieldRepository(session).register_field(document_id=doc.id, field_key="f")
    return field, user.id


def test_ancestors_walks_a_merge_dag(db_session: Session) -> None:
    repo = FieldRepository(db_session)
    field, uid = _bootstrap(db_session)

    v1 = repo.create_version(
        field_id=field.id, value="v1", value_hash=hash_value("v1"), parent_ids=[], created_by=uid
    )
    v2 = repo.create_version(
        field_id=field.id,
        value="v2",
        value_hash=hash_value("v2"),
        parent_ids=[v1.id],
        created_by=uid,
    )
    v3 = repo.create_version(
        field_id=field.id,
        value="v3",
        value_hash=hash_value("v3"),
        parent_ids=[v1.id, v2.id],  # merge node: two parents
        created_by=uid,
    )

    assert {a.id for a in repo.ancestors(v1.id)} == set()
    assert {a.id for a in repo.ancestors(v2.id)} == {v1.id}
    assert {a.id for a in repo.ancestors(v3.id)} == {v1.id, v2.id}
    assert v3.parent_version_id == [v1.id, v2.id]


def test_head_version_is_most_recent(db_session: Session) -> None:
    repo = FieldRepository(db_session)
    field, uid = _bootstrap(db_session)
    repo.create_version(
        field_id=field.id, value="a", value_hash=hash_value("a"), parent_ids=[], created_by=uid
    )
    head = repo.create_version(
        field_id=field.id, value="b", value_hash=hash_value("b"), parent_ids=[], created_by=uid
    )
    got = repo.get_head_version(field.id)
    assert got is not None
    assert got.id == head.id
