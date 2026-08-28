"""AuditRepository — append-only writes and filtered reads of ``audit_log``.

Every gate decision is permanent; there is no update or delete path here
(architecture doc section 4.1).
"""

from sqlalchemy.ext.asyncio import AsyncSession


class AuditRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
