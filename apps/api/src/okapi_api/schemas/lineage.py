"""Pydantic bodies for the lineage DAG endpoint (architecture doc section 4.2)."""

import uuid
from datetime import datetime

from pydantic import BaseModel


class LineageNode(BaseModel):
    id: uuid.UUID
    field_id: uuid.UUID
    value_hash: str
    status: str
    is_ai_generated: bool
    parent_version_id: list[uuid.UUID]
    created_at: datetime


class LineageEdgeRead(BaseModel):
    child_version_id: uuid.UUID
    parent_version_id: uuid.UUID
    edge_hash: str


class LineageGraph(BaseModel):
    document_id: uuid.UUID
    nodes: list[LineageNode]
    edges: list[LineageEdgeRead]
