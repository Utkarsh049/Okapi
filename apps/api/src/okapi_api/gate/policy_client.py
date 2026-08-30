"""Policy clients for the Verification & Compliance Gate (architecture doc section 6.1).

``OpaPolicyClient`` is the real one: it POSTs the gate input to the OPA sidecar and
reads back ``{allow, allowed_fields, reason}``. ``StubPolicyClient`` is an in-memory
stand-in for unit tests. Both satisfy the ``PolicyClient`` protocol the Gate depends on.
"""

from typing import Protocol

import httpx

from okapi_api.core.config import get_settings
from okapi_shared.constants import OPA_DECISION_PATH
from okapi_shared.contracts import PolicyInput, PolicyResult


class PolicyClient(Protocol):
    def evaluate(self, policy_input: PolicyInput) -> PolicyResult: ...


class OpaPolicyClient:
    """Talks to the OPA sidecar over HTTP."""

    def __init__(self, base_url: str | None = None) -> None:
        self._client = httpx.Client(base_url=base_url or get_settings().opa_url, timeout=5.0)

    def evaluate(self, policy_input: PolicyInput) -> PolicyResult:
        response = self._client.post(
            f"/v1/data/{OPA_DECISION_PATH}",
            json={"input": policy_input.model_dump(mode="json")},
        )
        response.raise_for_status()
        result = response.json().get("result")
        if result is None:
            # OPA returns {} when the decision path is undefined.
            return PolicyResult(allow=False, reason="policy decision path undefined")
        return PolicyResult.model_validate(result)


class StubPolicyClient:
    """Allow everything except explicit ``(field_key, action)`` denials. Tests only."""

    def __init__(self, denials: set[tuple[str, str]] | None = None) -> None:
        self._denials = denials or set()

    def evaluate(self, policy_input: PolicyInput) -> PolicyResult:
        key = (policy_input.field_key, policy_input.action.value)
        if key in self._denials:
            return PolicyResult(allow=False, reason=f"stub denied {key}")
        return PolicyResult(
            allow=True, allowed_fields=[policy_input.field_key], reason="stub allow"
        )
