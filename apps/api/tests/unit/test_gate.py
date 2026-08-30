import uuid

import pytest

from okapi_api.gate.gate import Gate, GateDenied
from okapi_api.gate.policy_client import StubPolicyClient
from okapi_shared.contracts import GateActor
from okapi_shared.enums import ActorType


class FakeAudit:
    def __init__(self) -> None:
        self.rows: list[dict] = []

    def record(self, **kwargs: object) -> dict:
        self.rows.append(kwargs)
        return kwargs


class FakeDoc:
    id = uuid.uuid4()
    doc_type = "patient_record"


class FakeField:
    def __init__(self, key: str, category: str | None = None) -> None:
        self.id = uuid.uuid4()
        self.field_key = key
        self.category = category
        self.requires_signoff = False


def _actor() -> GateActor:
    return GateActor(
        sub=str(uuid.uuid4()),
        role="clinician",
        actor_type=ActorType.HUMAN,
        attributes={"clearance_level": 3},
    )


def test_check_write_allows_and_writes_an_allow_row() -> None:
    audit = FakeAudit()
    gate = Gate(StubPolicyClient(), audit)  # type: ignore[arg-type]
    gate.check_write(actor=_actor(), document=FakeDoc(), field=FakeField("f"))
    assert audit.rows[0]["decision"].value == "allow"


def test_check_write_denied_raises_after_recording_the_deny() -> None:
    audit = FakeAudit()
    gate = Gate(StubPolicyClient(denials={("secret", "write")}), audit)  # type: ignore[arg-type]
    with pytest.raises(GateDenied):
        gate.check_write(actor=_actor(), document=FakeDoc(), field=FakeField("secret"))
    assert audit.rows[0]["decision"].value == "deny"


def test_check_fields_returns_only_the_allowed_subset() -> None:
    gate = Gate(StubPolicyClient(denials={("b", "read")}), FakeAudit())  # type: ignore[arg-type]
    allowed = gate.check_fields(
        actor=_actor(),
        document=FakeDoc(),
        fields=[FakeField("a"), FakeField("b"), FakeField("c")],
    )
    assert allowed == ["a", "c"]


def test_check_signoff_allows_and_writes_allow_row() -> None:
    audit = FakeAudit()
    gate = Gate(StubPolicyClient(), audit)  # type: ignore[arg-type]
    gate.check_signoff(actor=_actor(), document=FakeDoc(), field=FakeField("diagnosis"))
    assert len(audit.rows) == 1
    assert audit.rows[0]["action"] == "signoff"
    assert audit.rows[0]["decision"].value == "allow"


def test_check_signoff_denied_raises_after_recording_deny() -> None:
    audit = FakeAudit()
    gate = Gate(StubPolicyClient(denials={("restricted", "signoff")}), audit)  # type: ignore[arg-type]
    with pytest.raises(GateDenied):
        gate.check_signoff(actor=_actor(), document=FakeDoc(), field=FakeField("restricted"))
    assert len(audit.rows) == 1
    assert audit.rows[0]["action"] == "signoff"
    assert audit.rows[0]["decision"].value == "deny"
