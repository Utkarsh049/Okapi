"""Pydantic request/response bodies for the HTTP surface (architecture doc section 10).

No raw dicts cross a layer boundary. Contracts that also travel to the gate or a
future MCP server live in ``okapi_shared`` and are re-exported here.
"""

from okapi_shared.contracts import PolicyInput, PolicyResult

__all__ = ["PolicyInput", "PolicyResult"]
