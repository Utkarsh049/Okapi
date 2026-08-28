"""RetrievalService — orchestrates the read flow (architecture doc section 5.1).

Calls ``Gate.check`` for ``action="read"``, receives ``allowed_field_ids``, then asks
``RAGService`` to answer the question using only those fields, and writes one audit
row per field considered.
"""


class RetrievalService:
    """Read-path orchestration. Wire dependencies in during implementation."""
