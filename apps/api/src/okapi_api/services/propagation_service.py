"""PropagationService — dependent-field flagging (architecture doc section 4.5).

When a source field gets a new version, every ``field_references`` row pointing at it
is flipped to ``stale``. Synchronous in the prototype; an async fan-out post-prototype
(architecture doc section 11).
"""

import uuid

from okapi_api.repositories.field_repository import FieldRepository


class PropagationService:
    def __init__(self, fields: FieldRepository) -> None:
        self._fields = fields

    def flag_dependents(self, source_field_id: uuid.UUID) -> int:
        refs = self._fields.references_to(source_field_id)
        for ref in refs:
            self._fields.mark_reference_stale(ref.id)
        return len(refs)
