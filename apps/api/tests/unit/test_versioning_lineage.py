import uuid
from typing import Any

from okapi_api.core.hashing import hash_edge, hash_value
from okapi_api.services.lineage_service import LineageService
from okapi_api.services.versioning_service import VersioningService


class _Version:
    def __init__(self, **kw: Any) -> None:
        self.__dict__.update(kw)


class FakeFieldRepo:
    def __init__(self) -> None:
        self.versions: dict[uuid.UUID, _Version] = {}
        self.edges: list[dict] = []
        self._head: _Version | None = None

    def get_head_version(self, field_id: uuid.UUID) -> _Version | None:
        return self._head

    def create_version(
        self,
        *,
        field_id: uuid.UUID,
        value: str,
        value_hash: str,
        parent_ids: list[uuid.UUID],
        created_by: uuid.UUID,
        is_ai_generated: bool = False,
        amendment_note: str | None = None,
        status: str = "active",
    ) -> _Version:
        v = _Version(
            id=uuid.uuid4(),
            field_id=field_id,
            value=value,
            value_hash=value_hash,
            parent_version_id=list(parent_ids),
            created_by=created_by,
        )
        self.versions[v.id] = v
        self._head = v
        return v

    def get_version(self, version_id: uuid.UUID) -> _Version | None:
        return self.versions.get(version_id)

    def add_lineage_edge(
        self, *, child_version_id: uuid.UUID, parent_version_id: uuid.UUID, edge_hash: str
    ) -> dict:
        edge = {"child": child_version_id, "parent": parent_version_id, "edge_hash": edge_hash}
        self.edges.append(edge)
        return edge


def test_version_chain_hashes_content_and_chains_parents() -> None:
    repo = FakeFieldRepo()
    versioning = VersioningService(repo)  # type: ignore[arg-type]
    fid, uid = uuid.uuid4(), uuid.uuid4()

    v1 = versioning.create_version(field_id=fid, new_value="a", actor_id=uid)
    assert v1.value_hash == hash_value("a")
    assert v1.parent_version_id == []

    v2 = versioning.create_version(field_id=fid, new_value="b", actor_id=uid)
    assert v2.parent_version_id == [v1.id]


def test_lineage_edge_hash_matches_formula() -> None:
    repo = FakeFieldRepo()
    versioning = VersioningService(repo)  # type: ignore[arg-type]
    lineage = LineageService(repo)  # type: ignore[arg-type]
    fid, uid = uuid.uuid4(), uuid.uuid4()

    v1 = versioning.create_version(field_id=fid, new_value="a", actor_id=uid)
    v2 = versioning.create_version(field_id=fid, new_value="b", actor_id=uid)
    edges = lineage.link(v2, [v1.id])  # type: ignore[arg-type]

    assert edges[0]["edge_hash"] == hash_edge(str(v1.id), v1.value_hash, v2.value_hash)
