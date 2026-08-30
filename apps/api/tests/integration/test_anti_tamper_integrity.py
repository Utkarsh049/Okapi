"""Integration tests verifying Merkle anti-tamper security and performance benchmarks (Phase 08)."""

import time
import uuid

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session
from starlette.testclient import TestClient

from okapi_api.core.hashing import hash_edge, hash_value
from okapi_api.core.security import hash_password
from okapi_api.models import Document, User
from okapi_api.repositories.field_repository import FieldRepository
from okapi_api.services.integrity_service import IntegrityService
from okapi_api.services.versioning_service import VersioningService

pytestmark = pytest.mark.integration

API = "/api/v1"


def _seed_test_clinician(engine: Engine) -> tuple[str, str]:
    email = f"clinician-{uuid.uuid4()}@okapi.dev"
    password = "pass"
    with Session(engine) as session:
        user = User(
            email=email,
            full_name="Dr. Integrity Tester",
            role="clinician",
            password_hash=hash_password(password),
            attributes={"clearance_level": 3, "department": "cardiology"},
        )
        session.add(user)
        session.commit()
    return email, password


def test_legitimate_edits_yield_valid_merkle_signature(
    api_client: TestClient, engine: Engine
) -> None:
    email, password = _seed_test_clinician(engine)
    token = api_client.post(
        f"{API}/auth/token", data={"username": email, "password": password}
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Create doc and field
    doc = api_client.post(
        f"{API}/documents", json={"title": "Merkle Doc", "doc_type": "record"}, headers=headers
    ).json()
    field = api_client.post(
        f"{API}/documents/{doc['id']}/fields",
        json={"field_key": "patient.diagnosis", "value": "Initial Value"},
        headers=headers,
    ).json()

    # Edit twice
    v2 = api_client.patch(
        f"{API}/documents/{doc['id']}/fields/{field['id']}",
        json={"new_value": "Updated Value 2"},
        headers=headers,
    ).json()
    api_client.patch(
        f"{API}/documents/{doc['id']}/fields/{field['id']}",
        json={"new_value": "Updated Value 3", "parent_version_ids": [v2["id"]]},
        headers=headers,
    )

    # Check integrity
    resp = api_client.get(f"{API}/documents/{doc['id']}/integrity", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["signature_valid"] is True
    assert len(data["merkle_root"]) == 64


def test_single_point_sql_tampering_detected(api_client: TestClient, engine: Engine) -> None:
    email, password = _seed_test_clinician(engine)
    token = api_client.post(
        f"{API}/auth/token", data={"username": email, "password": password}
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    doc = api_client.post(
        f"{API}/documents", json={"title": "Tamper Target", "doc_type": "record"}, headers=headers
    ).json()
    field = api_client.post(
        f"{API}/documents/{doc['id']}/fields",
        json={"field_key": "patient.diagnosis", "value": "Original Untampered"},
        headers=headers,
    ).json()

    # Direct SQL UPDATE altering value without updating value_hash
    with Session(engine) as session:
        session.execute(
            text("UPDATE field_versions SET value = 'MALICIOUS_OVERWRITE' WHERE field_id = :fid"),
            {"fid": field["id"]},
        )
        session.commit()

    resp = api_client.get(f"{API}/documents/{doc['id']}/integrity", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is False
    assert len(data["value_hash_mismatches"]) >= 1


def test_coordinated_sql_tampering_detected_by_merkle_signature(
    api_client: TestClient, engine: Engine
) -> None:
    email, password = _seed_test_clinician(engine)
    token = api_client.post(
        f"{API}/auth/token", data={"username": email, "password": password}
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    doc = api_client.post(
        f"{API}/documents",
        json={"title": "Coordinated Tamper", "doc_type": "record"},
        headers=headers,
    ).json()
    field = api_client.post(
        f"{API}/documents/{doc['id']}/fields",
        json={"field_key": "patient.diagnosis", "value": "V1"},
        headers=headers,
    ).json()
    v2 = api_client.patch(
        f"{API}/documents/{doc['id']}/fields/{field['id']}",
        json={"new_value": "V2"},
        headers=headers,
    ).json()

    # Attacker directly alters field_versions.value, recalculates value_hash,
    # and recalculates lineage_edges.edge_hash inside Postgres
    tampered_val = "FORGED_V2"
    tampered_val_hash = hash_value(tampered_val)
    with Session(engine) as session:
        parent_v = session.execute(
            text("SELECT id, value_hash FROM field_versions WHERE value = 'V1'")
        ).fetchone()
        assert parent_v is not None
        p_id, p_hash = parent_v

        tampered_edge_hash = hash_edge(str(p_id), p_hash, tampered_val_hash)

        # Apply coordinated DB tampering
        session.execute(
            text("UPDATE field_versions SET value = :v, value_hash = :vh WHERE id = :id"),
            {"v": tampered_val, "vh": tampered_val_hash, "id": v2["id"]},
        )
        session.execute(
            text("UPDATE lineage_edges SET edge_hash = :eh WHERE child_version_id = :id"),
            {"eh": tampered_edge_hash, "id": v2["id"]},
        )
        session.commit()

    # The single-point checks pass, but Merkle Root and HMAC Cryptographic Signature MUST FAIL!
    resp = api_client.get(f"{API}/documents/{doc['id']}/integrity", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is False
    assert data["signature_valid"] is False
    assert len(data["root_mismatches"]) >= 1


def test_merkle_verification_performance_benchmark(engine: Engine) -> None:
    with Session(engine) as session:
        owner = User(
            email=f"bench-{uuid.uuid4()}@okapi.dev",
            full_name="Benchmarker",
            role="clinician",
            password_hash=hash_password("pass"),
            attributes={"clearance_level": 3},
        )
        session.add(owner)
        session.flush()

        doc = Document(title="Benchmark Document", doc_type="record", created_by=owner.id)
        session.add(doc)
        session.flush()

        field_repo = FieldRepository(session)
        version_service = VersioningService(field_repo)
        integrity_service = IntegrityService(field_repo)

        f = field_repo.register_field(document_id=doc.id, field_key="vitals.heart_rate")

        # Create 100 versioned mutations
        parent_id = None
        for i in range(100):
            p_ids = [parent_id] if parent_id else []
            v = version_service.create_version(
                field_id=f.id,
                new_value=f"HeartRate-{i}",
                actor_id=owner.id,
                parent_ids=p_ids,
            )
            parent_id = v.id
        session.commit()

        # Measure verification latency
        t_start = time.perf_counter()
        report = integrity_service.verify(doc.id)
        duration_ms = (time.perf_counter() - t_start) * 1000.0

        assert report["ok"] is True
        assert report["versions_checked"] == 100
        # Benchmark assertion: verification completes under 10 ms
        assert duration_ms < 10.0, f"Verification took {duration_ms:.2f} ms (threshold < 10.0 ms)"
