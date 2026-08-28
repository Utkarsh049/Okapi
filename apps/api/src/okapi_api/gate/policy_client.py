"""HTTP client wrapper around the OPA sidecar (architecture doc section 6.1).

The only component that talks to OPA. Sends ``{input: {...}}`` to
``/v1/data/<OPA_DECISION_PATH>`` and parses ``{result: {...}}`` back into a
:class:`PolicyResult`.
"""

import httpx

from okapi_api.core.config import get_settings
from okapi_shared.constants import OPA_DECISION_PATH
from okapi_shared.contracts import PolicyInput, PolicyResult


class PolicyClient:
    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client or httpx.AsyncClient(base_url=get_settings().opa_url)

    async def evaluate(self, policy_input: PolicyInput) -> PolicyResult:
        response = await self._client.post(
            f"/v1/data/{OPA_DECISION_PATH}",
            json={"input": policy_input.model_dump(mode="json")},
        )
        response.raise_for_status()
        payload = response.json()
        return PolicyResult.model_validate(payload["result"])
