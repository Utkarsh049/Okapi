"""RAGService — embeddings and field-scoped retrieval (architecture doc section 5.1).

``retrieve(document_id, allowed_field_ids, question)`` runs similarity search over
``pgvector`` embeddings restricted to the allowed fields, so the answer can only ever
be drawn from content the caller is permitted to see.
"""


class RAGService:
    """Field-scoped RAG. Wire the embedding store in during implementation."""
