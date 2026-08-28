"""LineageService — DAG construction and hash-chaining (architecture doc section 4.2).

``link(child_version, parent_version)`` writes a ``lineage_edges`` row with
``edge_hash = SHA256(parent_version_id + parent.value_hash + child.value_hash)`` so
every edge is independently verifiable. Multiple parents = a merge commit.
"""


class LineageService:
    """Edge linking. Wire the field repository in during implementation."""
