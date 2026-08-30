import uuid
from collections.abc import Sequence

from okapi_api.core.hashing import hash_value
from okapi_api.models import FieldVersion
from okapi_api.repositories.embedding_repository import EmbeddingRepository
from okapi_api.repositories.field_repository import FieldRepository
from okapi_api.services.embedding_service import EmbeddingService


class VersioningService:
    def __init__(
        self,
        fields: FieldRepository,
        embeddings: EmbeddingRepository | None = None,
        embed_service: EmbeddingService | None = None,
    ) -> None:
        self._fields = fields
        self._embeddings = embeddings or EmbeddingRepository(fields._session)
        self._embed_service = embed_service or EmbeddingService()

    def create_version(
        self,
        *,
        field_id: uuid.UUID,
        new_value: str,
        actor_id: uuid.UUID,
        parent_ids: Sequence[uuid.UUID] | None = None,
        is_ai_generated: bool = False,
        amendment_note: str | None = None,
        status: str = "active",
    ) -> FieldVersion:
        if parent_ids is None:
            head = self._fields.get_head_version(field_id)
            parent_ids = [head.id] if head is not None else []
        version = self._fields.create_version(
            field_id=field_id,
            value=new_value,
            value_hash=hash_value(new_value),
            parent_ids=list(parent_ids),
            created_by=actor_id,
            is_ai_generated=is_ai_generated,
            amendment_note=amendment_note,
            status=status,
        )

        # Automatically compute and store field vector embedding
        vector = self._embed_service.embed_text(new_value)
        self._embeddings.save_embedding(
            field_version_id=version.id,
            embedding=vector,
            chunk_text=new_value,
            model_name=self._embed_service.model_name,
        )

        return version
