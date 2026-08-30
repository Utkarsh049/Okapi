"""VersioningService — field-level version history (architecture doc section 4.1).

``create_version`` appends a ``field_versions`` row with the content hash and the
parent pointer array. This IS the "field-level versioning" mechanism.
"""

import uuid
from collections.abc import Sequence

from okapi_api.core.hashing import hash_value
from okapi_api.models import FieldVersion
from okapi_api.repositories.field_repository import FieldRepository


class VersioningService:
    def __init__(self, fields: FieldRepository) -> None:
        self._fields = fields

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
        return self._fields.create_version(
            field_id=field_id,
            value=new_value,
            value_hash=hash_value(new_value),
            parent_ids=list(parent_ids),
            created_by=actor_id,
            is_ai_generated=is_ai_generated,
            amendment_note=amendment_note,
            status=status,
        )
