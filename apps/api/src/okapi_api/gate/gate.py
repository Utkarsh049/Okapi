"""The Verification & Compliance Gate — the single choke point every service call passes.

Injected as a FastAPI dependency into every retrieving or mutating service method
(architecture doc section 3). It calls ``PolicyClient`` (OPA) and, for reads, the
integrity check, then returns the allowed subset of fields. A failed check raises
*before* any repository query runs (architecture doc section 1, principle 1).
"""

from okapi_api.gate.policy_client import PolicyClient
from okapi_shared.contracts import PolicyInput, PolicyResult


class GateDenied(Exception):
    """Raised when OPA denies an action. Handlers map this to HTTP 403 + audit(deny)."""


class Gate:
    def __init__(self, policy_client: PolicyClient) -> None:
        self._policy_client = policy_client

    async def check(self, policy_input: PolicyInput) -> PolicyResult:
        """Evaluate one field-scoped action. Raises :class:`GateDenied` on deny."""
        result = await self._policy_client.evaluate(policy_input)
        if not result.allow:
            raise GateDenied(result.reason)
        return result
