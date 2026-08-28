"""IntegrityService — Merkle verification (architecture doc sections 4.2 and 5.1).

Recomputes the Merkle root over all lineage edges for a document and compares it to
the stored root, detecting any modification made outside the API (e.g. a direct DB
edit bypassing the gate). Invoked by the Gate on the read path.
"""


class IntegrityService:
    """Chain verification. Wire the field repository in during implementation."""
