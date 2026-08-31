"""Adversarial tests for SQL tampering, orphaned edges, and broken DAGs (Phase 10)."""

import uuid

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from okapi_api.core.security import hash_password
from okapi_api.models import Document, User
from okapi_api.repositories.field_repository import FieldRepository
from okapi_api.services.integrity_service import IntegrityService
from okapi_api.services.lineage_service import LineageService
from okapi_api.services.versioning_service import VersioningService

pytestmark = pytest.mark.integration


def _seed_document_with_history(
    session: Session,
) -> tuple[Document, uuid.UUID, list[uuid.UUID]]:
    owner = User(
        email=f"tamper-target-{uuid.uuid4()}@okapi.dev",
        full_name="Target Owner",
        role="clinician",
        password_hash=hash_password("pass"),
        attributes={"clearance_level": 3},
    )
    session.add(owner)
    session.flush()

    doc = Document(title="Tamper Analysis Document", doc_type="record", created_by=owner.id)
    session.add(doc)
    session.flush()

    repo = FieldRepository(session)
    versioning = VersioningService(repo)
    lineage = LineageService(repo)

    f = repo.register_field(document_id=doc.id, field_key="patient.diagnosis")
    v1 = versioning.create_version(
        field_id=f.id, new_value="Hypertension", actor_id=owner.id, parent_ids=[]
    )
    v2 = versioning.create_version(
        field_id=f.id,
        new_value="Stage 2 Hypertension",
        actor_id=owner.id,
        parent_ids=[v1.id],
    )
    lineage.link(v2, [v1.id])
    session.commit()

    integrity = IntegrityService(repo)
    integrity.sign_document(doc.id)
    session.commit()

    return doc, f.id, [v1.id, v2.id]


def test_direct_sql_value_mutation_detected(engine: Engine) -> None:
    with Session(engine) as session:
        doc, field_id, version_ids = _seed_document_with_history(session)

        # Attacker executes direct SQL UPDATE on value without updating hash
        session.execute(
            text("UPDATE field_versions SET value = 'MALICIOUS_DIAGNOSIS' WHERE id = :vid"),
            {"vid": version_ids[0]},
        )
        session.commit()

        integrity = IntegrityService(FieldRepository(session))
        report = integrity.verify(doc.id)

        assert report["ok"] is False
        assert len(report["value_hash_mismatches"]) == 1
        assert report["value_hash_mismatches"][0]["version_id"] == str(version_ids[0])


def test_corrupted_edge_hash_detected(engine: Engine) -> None:
    with Session(engine) as session:
        doc, field_id, version_ids = _seed_document_with_history(session)

        # Attacker tampers with the edge_hash column in Postgres
        bogus_edge_hash = "0" * 64
        session.execute(
            text("UPDATE lineage_edges SET edge_hash = :eh WHERE child_version_id = :cid"),
            {"eh": bogus_edge_hash, "cid": version_ids[1]},
        )
        session.commit()

        integrity = IntegrityService(FieldRepository(session))
        report = integrity.verify(doc.id)

        assert report["ok"] is False
        assert len(report["edge_hash_mismatches"]) >= 1
        assert report["edge_hash_mismatches"][0]["stored"] == bogus_edge_hash


def test_tampered_merkle_signature_detected(engine: Engine) -> None:
    with Session(engine) as session:
        doc, field_id, version_ids = _seed_document_with_history(session)

        # Attacker overwrites the HMAC signature column in Postgres
        session.execute(
            text("UPDATE documents SET merkle_signature = '0123456789abcdef' WHERE id = :id"),
            {"id": doc.id},
        )
        session.commit()

        integrity = IntegrityService(FieldRepository(session))
        report = integrity.verify(doc.id)

        assert report["ok"] is False
        assert report["signature_valid"] is False


def test_tampered_merkle_root_detected(engine: Engine) -> None:
    with Session(engine) as session:
        doc, field_id, version_ids = _seed_document_with_history(session)

        # Attacker alters the stored merkle_root column in Postgres
        bogus_root = "a" * 64
        session.execute(
            text("UPDATE documents SET merkle_root = :root WHERE id = :id"),
            {"root": bogus_root, "id": doc.id},
        )
        session.commit()

        integrity = IntegrityService(FieldRepository(session))
        report = integrity.verify(doc.id)

        assert report["ok"] is False
        assert len(report["root_mismatches"]) == 1
