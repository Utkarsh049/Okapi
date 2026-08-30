"""EditService — orchestrates the write/edit flow (architecture doc section 5.2).

``Gate.check_write`` (raises on deny) -> ``VersioningService.create_version`` ->
``LineageService.link`` (hash-chain the edges) -> ``PropagationService.flag_dependents``.
The write is an amendment: a new version, never an overwrite.
"""

import uuid
from collections.abc import Sequence

from okapi_api.gate.gate import Gate
from okapi_api.models import Document, Field, FieldVersion
from okapi_api.repositories.field_repository import FieldRepository
from okapi_api.services.lineage_service import LineageService
from okapi_api.services.propagation_service import PropagationService
from okapi_api.services.versioning_service import VersioningService
from okapi_shared.contracts import GateActor


class EditService:
    def __init__(
        self,
        gate: Gate,
        versioning: VersioningService,
        lineage: LineageService,
        propagation: PropagationService,
        fields: FieldRepository,
    ) -> None:
        self._gate = gate
        self._versioning = versioning
        self._lineage = lineage
        self._propagation = propagation
        self._fields = fields

    def apply_edit(
        self,
        *,
        actor: GateActor,
        document: Document,
        field: Field,
        new_value: str,
        amendment_note: str | None = None,
        parent_version_ids: Sequence[uuid.UUID] | None = None,
        is_ai_generated: bool = False,
    ) -> FieldVersion:
        self._gate.check_write(actor=actor, document=document, field=field)

        if parent_version_ids is None:
            head = self._fields.get_head_version(field.id)
            parent_version_ids = [head.id] if head is not None else []

        version = self._versioning.create_version(
            field_id=field.id,
            new_value=new_value,
            actor_id=uuid.UUID(actor.sub),
            parent_ids=parent_version_ids,
            is_ai_generated=is_ai_generated,
            amendment_note=amendment_note,
        )
        self._lineage.link(version, parent_version_ids)
        self._propagation.flag_dependents(field.id)
        return version
