"""DocumentRepository — reads/writes for the ``documents`` container table.

Documents hold no versioned content; the interesting behaviour is one level down in
the field repository (architecture doc section 1, principle 2).
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from okapi_api.models import Document


class DocumentRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, *, title: str, doc_type: str, created_by: uuid.UUID) -> Document:
        doc = Document(title=title, doc_type=doc_type, created_by=created_by)
        self._session.add(doc)
        self._session.flush()
        return doc

    def get(self, document_id: uuid.UUID) -> Document | None:
        return self._session.get(Document, document_id)

    def list_all(self) -> list[Document]:
        return list(self._session.scalars(select(Document).order_by(Document.created_at)))
