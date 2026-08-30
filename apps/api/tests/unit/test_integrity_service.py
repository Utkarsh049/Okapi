import uuid
from typing import Any

from okapi_api.core.hashing import hash_edge, hash_value
from okapi_api.services.integrity_service import IntegrityService


class _Row:
    def __init__(self, **kw: Any) -> None:
        self.__dict__.update(kw)


class FakeRepo:
    def __init__(self, versions: list[_Row], edges: list[_Row]) -> None:
        self._versions = versions
        self._edges = edges

    def get_versions_for_document(self, document_id: uuid.UUID) -> list[_Row]:
        return self._versions

    def get_edges_for_document(self, document_id: uuid.UUID) -> list[_Row]:
        return self._edges


def _chain() -> tuple[_Row, _Row, _Row]:
    v1 = _Row(id=uuid.uuid4(), value="a", value_hash=hash_value("a"))
    v2 = _Row(id=uuid.uuid4(), value="b", value_hash=hash_value("b"))
    edge = _Row(
        id=uuid.uuid4(),
        parent_version_id=v1.id,
        child_version_id=v2.id,
        edge_hash=hash_edge(str(v1.id), v1.value_hash, v2.value_hash),
    )
    return v1, v2, edge


def test_verify_passes_for_an_untampered_chain() -> None:
    v1, v2, edge = _chain()
    report = IntegrityService(FakeRepo([v1, v2], [edge])).verify(uuid.uuid4())  # type: ignore[arg-type]
    assert report["ok"] is True
    assert report["value_hash_mismatches"] == []
    assert report["edge_hash_mismatches"] == []


def test_verify_flags_a_value_edited_directly_in_the_db() -> None:
    v1, v2, edge = _chain()
    v2.value = "tampered"  # value changed without updating value_hash
    report = IntegrityService(FakeRepo([v1, v2], [edge])).verify(uuid.uuid4())  # type: ignore[arg-type]
    assert report["ok"] is False
    assert len(report["value_hash_mismatches"]) == 1
