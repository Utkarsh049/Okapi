"""Audit log query endpoint (architecture doc sections 4.1 and 9).

Endpoint to implement: GET /audit (filterable by actor, document, decision).
The audit log is append-only; there is no write endpoint.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/audit", tags=["audit"])
