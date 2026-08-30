"""LineageService — DAG construction and hash-chaining (architecture doc section 4.2).

For every parent of a new version it writes a ``lineage_edges`` row whose
``edge_hash = SHA256(parent_id + parent.value_hash + child.value_hash)``. Two parents
means a merge commit.
"""

import uuid
from collections.abc import Sequence

from okapi_api.core.hashing import hash_edge
from okapi_api.models import FieldVersion, LineageEdge
from okapi_api.repositories.field_repository import FieldRepository


class LineageService:
    def __init__(self, fields: FieldRepository) -> None:
        self._fields = fields

    def link(self, child: FieldVersion, parent_ids: Sequence[uuid.UUID]) -> list[LineageEdge]:
        edges: list[LineageEdge] = []
        for parent_id in parent_ids:
            parent = self._fields.get_version(parent_id)
            if parent is None:
                continue
            edge_hash = hash_edge(str(parent_id), parent.value_hash, child.value_hash)
            edges.append(
                self._fields.add_lineage_edge(
                    child_version_id=child.id,
                    parent_version_id=parent_id,
                    edge_hash=edge_hash,
                )
            )
        return edges
