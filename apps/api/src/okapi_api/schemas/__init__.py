"""Pydantic request/response bodies for the HTTP surface (architecture doc section 10).

No raw dicts cross a layer boundary. Contracts that also travel to the gate or a
future MCP server live in ``okapi_shared`` and are re-exported here.
"""

from okapi_api.schemas.document import DocumentCreate, DocumentRead
from okapi_api.schemas.field import FieldPatch, FieldRead, FieldRegister, VersionRead
from okapi_shared.contracts import PolicyInput, PolicyResult

__all__ = [
    "DocumentCreate",
    "DocumentRead",
    "FieldPatch",
    "FieldRead",
    "FieldRegister",
    "PolicyInput",
    "PolicyResult",
    "VersionRead",
]
