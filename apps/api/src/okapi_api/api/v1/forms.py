"""AI-assisted form endpoints (architecture doc sections 5.3 and 9).

Endpoints to implement: POST /forms/{form_id}/autofill (gated per field),
POST /forms/{form_id}/submit (rejected if any field is pending_signoff).
"""

from fastapi import APIRouter

router = APIRouter(prefix="/forms", tags=["forms"])
