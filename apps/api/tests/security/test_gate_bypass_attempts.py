"""Adversarial tests verifying that the Verification Gate cannot be bypassed (Phase 10)."""

import uuid
from unittest.mock import MagicMock

import pytest

from okapi_api.gate.gate import Gate, GateDenied
from okapi_api.models import Document, Field
from okapi_api.services.edit_service import EditService
from okapi_api.services.form_fill_service import FormFillService
from okapi_api.services.retrieval_service import RetrievalService
from okapi_shared.contracts import GateActor
from okapi_shared.enums import ActorType


def _make_actor(
    role: str = "auditor",
    clearance: int = 1,
    actor_type: ActorType = ActorType.HUMAN,
) -> GateActor:
    return GateActor(
        sub=str(uuid.uuid4()),
        role=role,
        actor_type=actor_type,
        attributes={"clearance_level": clearance, "department": "compliance"},
    )


def test_edit_service_strictly_blocks_unauthorized_actor() -> None:
    gate_mock = MagicMock(spec=Gate)
    gate_mock.check_write.side_effect = GateDenied("Actor lacks write clearance")

    versioning_mock = MagicMock()
    lineage_mock = MagicMock()
    propagation_mock = MagicMock()
    fields_mock = MagicMock()

    service = EditService(
        gate=gate_mock,
        versioning=versioning_mock,
        lineage=lineage_mock,
        propagation=propagation_mock,
        fields=fields_mock,
    )

    actor = _make_actor(role="auditor", clearance=1)
    doc = Document(id=uuid.uuid4(), title="Restricted Doc", doc_type="record")
    field = Field(id=uuid.uuid4(), document_id=doc.id, field_key="patient.ssn")

    with pytest.raises(GateDenied) as exc_info:
        service.apply_edit(
            actor=actor,
            document=doc,
            field=field,
            new_value="000-11-2222",
        )

    assert "lacks write clearance" in str(exc_info.value)
    # Ensure no version was created or linked
    versioning_mock.create_version.assert_not_called()
    lineage_mock.link.assert_not_called()


def test_retrieval_service_filters_unauthorized_fields() -> None:
    gate_mock = MagicMock(spec=Gate)
    gate_mock.check_fields.return_value = ["vitals.heart_rate"]

    fields_mock = MagicMock()
    rag_mock = MagicMock()
    rag_mock.retrieve.return_value = {
        "answer": "Patient heart rate is 72 bpm.",
        "fields": {"vitals.heart_rate": "72"},
    }

    f_vitals = Field(id=uuid.uuid4(), field_key="vitals.heart_rate")
    f_ssn = Field(id=uuid.uuid4(), field_key="patient.ssn")
    fields_mock.get_fields_for_document.return_value = [f_vitals, f_ssn]

    retrieval = RetrievalService(gate=gate_mock, fields=fields_mock, rag=rag_mock)

    actor = _make_actor(role="researcher", clearance=1)
    doc = Document(id=uuid.uuid4(), title="Patient Record", doc_type="record")

    response = retrieval.query(
        actor=actor,
        document=doc,
        question="What is the patient SSN and heart rate?",
    )

    assert response["allowed_fields"] == ["vitals.heart_rate"]
    assert "patient.ssn" in response["withheld_fields"]
    assert response["fields"] == {"vitals.heart_rate": "72"}


def test_form_fill_service_gated_against_unauthorized_drafting() -> None:
    gate_mock = MagicMock(spec=Gate)
    gate_mock.check_fields.side_effect = GateDenied("AI agent forbidden from accessing document")

    docs_mock = MagicMock()
    fields_mock = MagicMock()
    versioning_mock = MagicMock()
    embeddings_mock = MagicMock()

    service = FormFillService(
        gate=gate_mock,
        docs=docs_mock,
        fields=fields_mock,
        versioning=versioning_mock,
        embeddings=embeddings_mock,
    )

    actor = _make_actor(role="ai_agent", clearance=1, actor_type=ActorType.AI_AGENT)
    target_id = uuid.uuid4()
    source_id = uuid.uuid4()

    form_doc = Document(id=target_id, title="Target Form", doc_type="form")
    docs_mock.get.return_value = form_doc
    fields_mock.get_fields_for_document.return_value = [
        Field(id=uuid.uuid4(), document_id=target_id, field_key="patient.diagnosis")
    ]

    with pytest.raises(GateDenied):
        service.autofill_form(
            actor=actor,
            form_document_id=target_id,
            source_document_ids=[source_id],
        )
