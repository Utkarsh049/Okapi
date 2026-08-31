"""SQLAlchemy ORM models.

Every model is imported here so ``Base.metadata`` is complete for Alembic autogenerate
and for ``create_all`` in tests.
"""

from okapi_api.models.audit import AuditLog
from okapi_api.models.base import Base
from okapi_api.models.compliance import ComplianceRule
from okapi_api.models.document import Document
from okapi_api.models.field import Field, FieldVersion
from okapi_api.models.field_embedding import FieldEmbedding
from okapi_api.models.lineage import LineageEdge
from okapi_api.models.reference import FieldReference
from okapi_api.models.user import User

__all__ = [
    "AuditLog",
    "Base",
    "ComplianceRule",
    "Document",
    "Field",
    "FieldEmbedding",
    "FieldReference",
    "FieldVersion",
    "LineageEdge",
    "User",
]
