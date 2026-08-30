"""IntegrityService — Merkle / hash-chain verification (architecture doc sections 4.2, 5.1).

``verify`` recomputes every ``value_hash`` and every ``edge_hash`` for a document and
reports mismatches, detecting any change made outside the API (e.g. a direct DB edit
that bypassed the Gate). ``merkle_root`` folds the sorted edge hashes for display.

Note: there is no stored root column in the prototype schema, so a coordinated tamper
of a value *and* all of its incident hashes would not be caught here. Independent
recomputation still catches every single-point edit — enough for the demo.
"""

import hashlib
import uuid

from okapi_api.core.hashing import hash_edge, hash_value
from okapi_api.repositories.field_repository import FieldRepository
from okapi_shared.constants import HASH_ALGORITHM


class IntegrityService:
    def __init__(self, fields: FieldRepository) -> None:
        self._fields = fields

    def verify(self, document_id: uuid.UUID) -> dict[str, object]:
        versions = {v.id: v for v in self._fields.get_versions_for_document(document_id)}
        edges = self._fields.get_edges_for_document(document_id)

        value_mismatches: list[dict[str, str]] = []
        for version in versions.values():
            recomputed = hash_value(version.value)
            if recomputed != version.value_hash:
                value_mismatches.append(
                    {
                        "version_id": str(version.id),
                        "stored": version.value_hash,
                        "recomputed": recomputed,
                    }
                )

        edge_mismatches: list[dict[str, str]] = []
        for edge in edges:
            parent = versions.get(edge.parent_version_id)
            child = versions.get(edge.child_version_id)
            if parent is None or child is None:
                edge_mismatches.append({"edge_id": str(edge.id), "error": "dangling edge"})
                continue
            recomputed = hash_edge(str(edge.parent_version_id), parent.value_hash, child.value_hash)
            if recomputed != edge.edge_hash:
                edge_mismatches.append(
                    {
                        "edge_id": str(edge.id),
                        "stored": edge.edge_hash,
                        "recomputed": recomputed,
                    }
                )

        return {
            "document_id": str(document_id),
            "ok": not value_mismatches and not edge_mismatches,
            "versions_checked": len(versions),
            "edges_checked": len(edges),
            "value_hash_mismatches": value_mismatches,
            "edge_hash_mismatches": edge_mismatches,
            "merkle_root": self._merkle_root([e.edge_hash for e in edges]),
        }

    def merkle_root(self, document_id: uuid.UUID) -> str:
        edges = self._fields.get_edges_for_document(document_id)
        return self._merkle_root([e.edge_hash for e in edges])

    @staticmethod
    def _merkle_root(edge_hashes: list[str]) -> str:
        if not edge_hashes:
            return hashlib.new(HASH_ALGORITHM, b"").hexdigest()
        acc = ""
        for h in sorted(edge_hashes):
            acc = hashlib.new(HASH_ALGORITHM, f"{acc}{h}".encode()).hexdigest()
        return acc
