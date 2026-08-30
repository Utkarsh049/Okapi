"""Integration tests for field vector embeddings and semantic search (Phase 05)."""

import uuid

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from okapi_api.core.security import hash_password
from okapi_api.models import Document, User
from okapi_api.repositories.embedding_repository import EmbeddingRepository
from okapi_api.repositories.field_repository import FieldRepository
from okapi_api.services.embedding_service import EmbeddingService
from okapi_api.services.versioning_service import VersioningService

pytestmark = pytest.mark.integration


def _seed_test_user(engine: Engine) -> User:
    email = f"user-{uuid.uuid4()}@okapi.dev"
    with Session(engine) as session:
        user = User(
            email=email,
            full_name="Dr. Embedding Tester",
            role="clinician",
            password_hash=hash_password("pass"),
            attributes={"clearance_level": 3},
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user


def test_field_version_automatically_generates_embedding(engine: Engine) -> None:
    user = _seed_test_user(engine)
    with Session(engine) as session:
        doc = Document(title="Embedding Test Record", doc_type="record", created_by=user.id)
        session.add(doc)
        session.flush()

        field_repo = FieldRepository(session)
        version_service = VersioningService(field_repo)

        field = field_repo.register_field(
            document_id=doc.id, field_key="patient.diagnosis", category="phi"
        )
        version = version_service.create_version(
            field_id=field.id,
            new_value="Severe stage 2 hypertension with acute headache",
            actor_id=user.id,
        )
        session.commit()

        # Check embedding exists in field_embeddings table
        emb_repo = EmbeddingRepository(session)
        emb = emb_repo.get_by_version_id(version.id)
        assert emb is not None
        assert len(emb.embedding) == 384
        assert "hypertension" in emb.chunk_text.lower()


def test_document_semantic_similarity_search(engine: Engine) -> None:
    user = _seed_test_user(engine)
    with Session(engine) as session:
        doc = Document(title="Cardiology Record", doc_type="record", created_by=user.id)
        session.add(doc)
        session.flush()

        field_repo = FieldRepository(session)
        version_service = VersioningService(field_repo)

        # Create 3 distinct fields
        f1 = field_repo.register_field(
            document_id=doc.id, field_key="patient.diagnosis", category="phi"
        )
        version_service.create_version(
            field_id=f1.id, new_value="Essential primary hypertension", actor_id=user.id
        )

        f2 = field_repo.register_field(
            document_id=doc.id, field_key="patient.care_plan", category="clinical"
        )
        version_service.create_version(
            field_id=f2.id, new_value="Prescribe ACE inhibitor and beta blocker", actor_id=user.id
        )

        f3 = field_repo.register_field(
            document_id=doc.id, field_key="study.cohort_size", category="research"
        )
        version_service.create_version(
            field_id=f3.id, new_value="Cohort 240 patients enrolled", actor_id=user.id
        )
        session.commit()

        emb_service = EmbeddingService()
        emb_repo = EmbeddingRepository(session)

        # Search for blood pressure diagnosis
        query_vec = emb_service.embed_text("blood pressure and hypertension diagnosis")
        results = emb_repo.search_similar(document_id=doc.id, query_embedding=query_vec, limit=2)

        assert len(results) >= 1
        top_emb, top_score = results[0]
        assert "hypertension" in top_emb.chunk_text.lower()
        assert top_score > 0.0

        # Search with field restriction (only allow f2 and f3)
        restricted_results = emb_repo.search_similar(
            document_id=doc.id,
            query_embedding=query_vec,
            limit=2,
            allowed_field_ids=[f2.id, f3.id],
        )
        # f1 must not appear in restricted results
        assert all(emb.field_version_id != f1.id for emb, _ in restricted_results)
