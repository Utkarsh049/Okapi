"""Okapi shared contracts — types that cross layer boundaries.

No I/O and no framework imports live here, so this package is safe to import from
any layer of the API service or from a future MCP tool surface.
"""

from okapi_shared.contracts import GateActor, PolicyInput, PolicyResult
from okapi_shared.enums import ActorType, Decision, EdgeAction, ReferenceStatus

__all__ = [
    "ActorType",
    "Decision",
    "EdgeAction",
    "GateActor",
    "PolicyInput",
    "PolicyResult",
    "ReferenceStatus",
]
