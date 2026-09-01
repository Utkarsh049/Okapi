"""Pydantic bodies for auth endpoints beyond the standard OAuth2 token form."""

from pydantic import BaseModel


class DelegateRequest(BaseModel):
    """Issue a scoped token letting an AI agent act on the caller's behalf
    (architecture doc — HIPAA AI delegation boundary)."""

    agent_email: str
