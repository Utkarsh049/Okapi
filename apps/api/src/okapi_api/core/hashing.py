"""Deterministic hashing for the lineage hash chain (architecture doc section 4.2).

Plain library code, no model calls — this is part of the auditable deterministic core.
"""

import hashlib

from okapi_shared.constants import HASH_ALGORITHM


def hash_value(value: str) -> str:
    """Content hash stored on every ``field_versions`` row."""
    return hashlib.new(HASH_ALGORITHM, value.encode("utf-8")).hexdigest()


def hash_edge(parent_version_id: str, parent_value_hash: str, child_value_hash: str) -> str:
    """Edge hash: ``SHA256(parent_id + parent.value_hash + child.value_hash)`` (arch doc 4.2)."""
    payload = f"{parent_version_id}{parent_value_hash}{child_value_hash}"
    return hashlib.new(HASH_ALGORITHM, payload.encode("utf-8")).hexdigest()
