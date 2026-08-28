"""Document container + field-scoped retrieval/edit endpoints (architecture doc section 9).

Router functions stay ~5 lines: parse input, call one service method, return.
Endpoints to implement: POST /documents, POST /documents/{id}/fields,
GET /documents/{id}/query, PATCH /documents/{id}/fields/{field_id},
GET /documents/{id}/lineage.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/documents", tags=["documents"])
