"""FieldRepository — ``fields``, ``field_versions``, ``lineage_edges``, ``field_references``.

Home of the recursive-CTE DAG traversal (ancestor lookup, dependency flagging) from
architecture doc section 4.3.
"""

from sqlalchemy.ext.asyncio import AsyncSession


class FieldRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
