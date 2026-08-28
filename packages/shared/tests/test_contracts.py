from okapi_shared import ActorType, EdgeAction, PolicyResult
from okapi_shared.contracts import GateActor, PolicyInput


def test_policy_result_defaults_to_empty_allowed_fields() -> None:
    result = PolicyResult(allow=False, reason="no matching grant")
    assert result.allowed_fields == []


def test_policy_input_roundtrips_through_json() -> None:
    payload = PolicyInput(
        actor=GateActor(sub="u1", role="clinician", actor_type=ActorType.HUMAN),
        action=EdgeAction.READ,
        field_key="patient.dob",
    )
    assert PolicyInput.model_validate(payload.model_dump()) == payload
