"""Unit tests for FormFillService and Patent 4.6 Gated Sign-Off Barrier."""

import uuid
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from okapi_api.models import Document, Field, FieldVersion
from okapi_api.services.form_fill_service import FormFillService
from okapi_shared.contracts import GateActor
from okapi_shared.enums import ActorType


def _make_actor(role: str = "clinician") -> GateActor:
    return GateActor(
        sub=str(uuid.uuid4()),
        role=role,
        actor_type=ActorType.HUMAN,
        acting_on_behalf_of=None,
        attributes={"clearance_level": 3},
    )


def test_submit_form_blocked_when_pending_signoff() -> None:
    gate_mock = MagicMock()
    docs_mock = MagicMock()
    fields_mock = MagicMock()
    versioning_mock = MagicMock()

    form_id = uuid.uuid4()
    form_doc = Document(id=form_id, title="Discharge Summary", doc_type="form")
    docs_mock.get.return_value = form_doc

    f1 = Field(
        id=uuid.uuid4(), document_id=form_id, field_key="patient.diagnosis", requires_signoff=True
    )
    f2 = Field(
        id=uuid.uuid4(), document_id=form_id, field_key="vitals.heart_rate", requires_signoff=False
    )
    fields_mock.get_fields_for_document.return_value = [f1, f2]

    v1 = FieldVersion(
        id=uuid.uuid4(), field_id=f1.id, value="Hypertension", status="pending_signoff"
    )
    v2 = FieldVersion(id=uuid.uuid4(), field_id=f2.id, value="72", status="active")

    def _get_head(fid: uuid.UUID) -> FieldVersion:
        return v1 if fid == f1.id else v2

    fields_mock.get_head_version.side_effect = _get_head

    service = FormFillService(
        gate=gate_mock,
        docs=docs_mock,
        fields=fields_mock,
        versioning=versioning_mock,
    )

    actor = _make_actor()
    with pytest.raises(HTTPException) as exc_info:
        service.submit_form(actor=actor, form_document_id=form_id)

    assert exc_info.value.status_code == 422
    detail = exc_info.value.detail
    assert "blocked" in detail["message"].lower()
    assert len(detail["unapproved_fields"]) == 1
    assert detail["unapproved_fields"][0]["field_key"] == "patient.diagnosis"


def test_submit_form_succeeds_when_all_active() -> None:
    gate_mock = MagicMock()
    docs_mock = MagicMock()
    fields_mock = MagicMock()
    versioning_mock = MagicMock()

    form_id = uuid.uuid4()
    form_doc = Document(id=form_id, title="Discharge Summary", doc_type="form")
    docs_mock.get.return_value = form_doc

    f1 = Field(
        id=uuid.uuid4(), document_id=form_id, field_key="patient.diagnosis", requires_signoff=True
    )
    fields_mock.get_fields_for_document.return_value = [f1]

    v1 = FieldVersion(id=uuid.uuid4(), field_id=f1.id, value="Hypertension", status="active")
    fields_mock.get_head_version.return_value = v1

    service = FormFillService(
        gate=gate_mock,
        docs=docs_mock,
        fields=fields_mock,
        versioning=versioning_mock,
    )

    actor = _make_actor()
    resp = service.submit_form(actor=actor, form_document_id=form_id)

    assert resp.status_code if hasattr(resp, "status_code") else resp.status == "submitted"
    assert "patient.diagnosis" in resp.signed_off_fields
