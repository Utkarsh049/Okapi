"""``lineage_edges`` — hash-linked DAG edges (architecture doc section 4.2).

``edge_hash = SHA256(parent_version_id + parent.value_hash + child.value_hash)`` so each
edge is independently verifiable and the Merkle root over a document's edges detects any
change made outside the API.
"""

import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from okapi_api.models.base import Base


class LineageEdge(Base):
    __tablename__ = "lineage_edges"
    __table_args__ = (
        UniqueConstraint("child_version_id", "parent_version_id", name="uq_edge_child_parent"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    child_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("field_versions.id", ondelete="CASCADE"), index=True
    )
    parent_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("field_versions.id", ondelete="CASCADE"), index=True
    )
    edge_hash: Mapped[str] = mapped_column(String(64))
