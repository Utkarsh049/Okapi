"""Field-level actions not nested under a document path (architecture doc section 9).

Endpoints to implement: POST /fields/{field_id}/signoff (human approval for a gated field).
"""

from fastapi import APIRouter

router = APIRouter(prefix="/fields", tags=["fields"])
