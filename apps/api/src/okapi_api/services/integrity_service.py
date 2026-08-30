"""IntegrityService — Merkle / hash-chain verification & cryptographic anti-tamper (Phase 08).

Verifies individual value hashes, DAG edge hash chains, and HMAC-signed document Merkle roots
to detect unauthorized direct database edits and coordinated out-of-band tampering.
"""

import uuid
from datetime import UTC, datetime

from okapi_api.core.config import get_settings
from okapi_api.core.hashing import (
    compute_merkle_root,
    hash_edge,
    hash_value,
    sign_merkle_root,
    verify_merkle_signature,
)
from okapi_api.repositories.document_repository import DocumentRepository
from okapi_api.repositories.field_repository import FieldRepository


class IntegrityService:
    def __init__(
        self,
        fields: FieldRepository,
        docs: DocumentRepository | None = None,
    ) -> None:
        self._fields = fields
        if docs is not None:
            self._docs: DocumentRepository | None = docs
        elif hasattr(fields, "_session") and fields._session is not None:
            self._docs = DocumentRepository(fields._session)
        else:
            self._docs = None

    def sign_document(self, document_id: uuid.UUID) -> tuple[str, str]:
        """Compute Merkle root and HMAC-SHA256 signature, persisting them to the document."""
        edges = self._fields.get_edges_for_document(document_id)
        merkle_root = compute_merkle_root([e.edge_hash for e in edges])
        secret = get_settings().jwt_secret
        signature = sign_merkle_root(merkle_root, secret)

        if self._docs is not None:
            self._docs.update_merkle_root(
                document_id=document_id,
                merkle_root=merkle_root,
                merkle_signature=signature,
            )
        return merkle_root, signature

    def verify(self, document_id: uuid.UUID) -> dict[str, object]:
        """Verify entire document integrity: value hashes, edge hashes, and Merkle signature."""
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

        recomputed_root = compute_merkle_root([e.edge_hash for e in edges])
        secret = get_settings().jwt_secret

        doc = self._docs.get(document_id) if self._docs is not None else None
        stored_root = doc.merkle_root if doc is not None else None
        stored_sig = doc.merkle_signature if doc is not None else None

        # If a stored root exists, check matching and valid signature
        root_matches = True
        signature_valid = True
        root_mismatches: list[dict[str, str]] = []

        if stored_root is not None and stored_root != recomputed_root:
            root_matches = False
            root_mismatches.append({"stored": stored_root, "recomputed": recomputed_root})

        if stored_sig is not None:
            signature_valid = verify_merkle_signature(recomputed_root, stored_sig, secret)
        elif stored_root is not None:
            signature_valid = False

        anti_tamper_passed = (
            (not value_mismatches)
            and (not edge_mismatches)
            and root_matches
            and signature_valid
        )

        if doc is not None:
            doc.last_verified_at = datetime.now(UTC)
            if hasattr(self._fields, "_session") and self._fields._session is not None:
                self._fields._session.flush()

        return {
            "document_id": str(document_id),
            "ok": anti_tamper_passed,
            "anti_tamper_passed": anti_tamper_passed,
            "versions_checked": len(versions),
            "edges_checked": len(edges),
            "merkle_root": recomputed_root,
            "stored_merkle_root": stored_root,
            "signature_valid": signature_valid,
            "root_mismatches": root_mismatches,
            "value_hash_mismatches": value_mismatches,
            "edge_hash_mismatches": edge_mismatches,
        }

    def merkle_root(self, document_id: uuid.UUID) -> str:
        edges = self._fields.get_edges_for_document(document_id)
        return compute_merkle_root([e.edge_hash for e in edges])
