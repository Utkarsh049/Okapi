"""DocumentRepository — reads/writes for the ``documents`` container table.

Documents hold no versioned content; the interesting behaviour is one level down in
the field repository (architecture doc section 1, principle 2).
"""

from sqlalchemy.ext.asyncio import AsyncSession


class DocumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
