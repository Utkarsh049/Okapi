"""FieldRepository — ``fields``, ``field_versions``, ``lineage_edges``, ``field_references``.

Home of the recursive-CTE DAG traversal (ancestor lookup) from architecture doc §4.3
and the reference walk that powers propagation (§4.5).
"""

import uuid
from collections.abc import Sequence

from sqlalchemy import select, text, update
from sqlalchemy.orm import Session

from okapi_api.models import Field, FieldReference, FieldVersion, LineageEdge
from okapi_shared.enums import ReferenceStatus


class FieldRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    # ------------------------------------------------------------------ fields
    def register_field(
        self,
        *,
        document_id: uuid.UUID,
        field_key: str,
        field_type: str = "text",
        requires_signoff: bool = False,
        category: str | None = None,
    ) -> Field:
        field = Field(
            document_id=document_id,
            field_key=field_key,
            field_type=field_type,
            requires_signoff=requires_signoff,
            category=category,
        )
        self._session.add(field)
        self._session.flush()
        return field

    def get_field(self, field_id: uuid.UUID) -> Field | None:
        return self._session.get(Field, field_id)

    def get_field_by_key(self, document_id: uuid.UUID, field_key: str) -> Field | None:
        stmt = select(Field).where(Field.document_id == document_id, Field.field_key == field_key)
        return self._session.scalars(stmt).first()

    def get_fields_for_document(self, document_id: uuid.UUID) -> list[Field]:
        stmt = select(Field).where(Field.document_id == document_id).order_by(Field.field_key)
        return list(self._session.scalars(stmt))

    # ---------------------------------------------------------------- versions
    def create_version(
        self,
        *,
        field_id: uuid.UUID,
        value: str,
        value_hash: str,
        parent_ids: Sequence[uuid.UUID],
        created_by: uuid.UUID,
        is_ai_generated: bool = False,
        amendment_note: str | None = None,
        status: str = "active",
    ) -> FieldVersion:
        version = FieldVersion(
            field_id=field_id,
            value=value,
            value_hash=value_hash,
            parent_version_id=list(parent_ids),
            created_by=created_by,
            is_ai_generated=is_ai_generated,
            amendment_note=amendment_note,
            status=status,
        )
        self._session.add(version)
        self._session.flush()
        return version

    def get_version(self, version_id: uuid.UUID) -> FieldVersion | None:
        return self._session.get(FieldVersion, version_id)

    def get_head_version(self, field_id: uuid.UUID) -> FieldVersion | None:
        """Most recent version on the field (the default parent for the next edit)."""
        stmt = (
            select(FieldVersion)
            .where(FieldVersion.field_id == field_id)
            .order_by(FieldVersion.created_at.desc())
        )
        return self._session.scalars(stmt).first()

    def list_versions(self, field_id: uuid.UUID) -> list[FieldVersion]:
        stmt = (
            select(FieldVersion)
            .where(FieldVersion.field_id == field_id)
            .order_by(FieldVersion.created_at)
        )
        return list(self._session.scalars(stmt))

    def set_version_status(self, version_id: uuid.UUID, status: str) -> None:
        self._session.execute(
            update(FieldVersion).where(FieldVersion.id == version_id).values(status=status)
        )

    # ----------------------------------------------------------------- lineage
    def add_lineage_edge(
        self, *, child_version_id: uuid.UUID, parent_version_id: uuid.UUID, edge_hash: str
    ) -> LineageEdge:
        edge = LineageEdge(
            child_version_id=child_version_id,
            parent_version_id=parent_version_id,
            edge_hash=edge_hash,
        )
        self._session.add(edge)
        self._session.flush()
        return edge

    def get_edges_for_document(self, document_id: uuid.UUID) -> list[LineageEdge]:
        stmt = (
            select(LineageEdge)
            .join(FieldVersion, LineageEdge.child_version_id == FieldVersion.id)
            .join(Field, FieldVersion.field_id == Field.id)
            .where(Field.document_id == document_id)
        )
        return list(self._session.scalars(stmt))

    def get_versions_for_document(self, document_id: uuid.UUID) -> list[FieldVersion]:
        stmt = (
            select(FieldVersion)
            .join(Field, FieldVersion.field_id == Field.id)
            .where(Field.document_id == document_id)
            .order_by(FieldVersion.created_at)
        )
        return list(self._session.scalars(stmt))

    def ancestors(self, version_id: uuid.UUID) -> list[FieldVersion]:
        """All transitive parents of a version, via a recursive CTE (architecture doc §4.3).

        ``UNION`` (not ``UNION ALL``) so a diamond/merge in the DAG is visited once.
        """
        cte = text("""
            WITH RECURSIVE ancestry AS (
                SELECT id, parent_version_id
                FROM field_versions
                WHERE id = :start
                UNION
                SELECT fv.id, fv.parent_version_id
                FROM field_versions fv
                JOIN ancestry a ON fv.id = ANY(a.parent_version_id)
            )
            SELECT id FROM ancestry WHERE id <> :start
            """)
        ids = [row[0] for row in self._session.execute(cte, {"start": version_id})]
        if not ids:
            return []
        return list(self._session.scalars(select(FieldVersion).where(FieldVersion.id.in_(ids))))

    # -------------------------------------------------------------- references
    def add_reference(
        self,
        *,
        source_field_id: uuid.UUID,
        referencing_document_id: uuid.UUID,
        referencing_field_id: uuid.UUID,
    ) -> FieldReference:
        ref = FieldReference(
            source_field_id=source_field_id,
            referencing_document_id=referencing_document_id,
            referencing_field_id=referencing_field_id,
        )
        self._session.add(ref)
        self._session.flush()
        return ref

    def references_to(self, source_field_id: uuid.UUID) -> list[FieldReference]:
        stmt = select(FieldReference).where(FieldReference.source_field_id == source_field_id)
        return list(self._session.scalars(stmt))

    def mark_reference_stale(self, reference_id: uuid.UUID) -> None:
        self._session.execute(
            update(FieldReference)
            .where(FieldReference.id == reference_id)
            .values(status=ReferenceStatus.STALE)
        )
