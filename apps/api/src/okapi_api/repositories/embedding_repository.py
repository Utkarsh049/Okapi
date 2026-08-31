"""Embedding Repository for storing and retrieving field version vector embeddings."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from okapi_api.models import Field, FieldEmbedding, FieldVersion
from okapi_api.services.embedding_service import EmbeddingService


class EmbeddingRepository:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._embed_service = EmbeddingService()

    def save_embedding(
        self,
        field_version_id: uuid.UUID,
        embedding: list[float],
        chunk_text: str,
        model_name: str = "okapi-embed-v1",
    ) -> FieldEmbedding:
        """Persist or update embedding vector for a specific field version."""
        existing = self._session.scalars(
            select(FieldEmbedding).where(FieldEmbedding.field_version_id == field_version_id)
        ).first()

        if existing:
            existing.embedding = embedding
            existing.chunk_text = chunk_text
            existing.model_name = model_name
            self._session.flush()
            return existing

        emb_obj = FieldEmbedding(
            field_version_id=field_version_id,
            embedding=embedding,
            chunk_text=chunk_text,
            model_name=model_name,
        )
        self._session.add(emb_obj)
        self._session.flush()
        return emb_obj

    def get_by_version_id(self, field_version_id: uuid.UUID) -> FieldEmbedding | None:
        return self._session.scalars(
            select(FieldEmbedding).where(FieldEmbedding.field_version_id == field_version_id)
        ).first()

    def search_similar(
        self,
        document_id: uuid.UUID,
        query_embedding: list[float],
        limit: int = 5,
        allowed_field_ids: list[uuid.UUID] | None = None,
    ) -> list[tuple[FieldEmbedding, float]]:
        """Search top-k most similar field embeddings in document, constrained by allowed fields."""
        stmt = (
            select(FieldEmbedding, Field.id)
            .join(FieldVersion, FieldEmbedding.field_version_id == FieldVersion.id)
            .join(Field, FieldVersion.field_id == Field.id)
            .where(Field.document_id == document_id)
        )

        if allowed_field_ids is not None:
            stmt = stmt.where(Field.id.in_(allowed_field_ids))

        rows = self._session.execute(stmt).all()
        scored: list[tuple[FieldEmbedding, float]] = []

        for emb, _field_id in rows:
            score = self._embed_service.cosine_similarity(query_embedding, emb.embedding)
            scored.append((emb, score))

        # Sort descending by cosine similarity score
        scored.sort(key=lambda item: item[1], reverse=True)
        return scored[:limit]
