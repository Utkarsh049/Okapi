"""Adversarial tests verifying multi-tenant and cross-document boundary isolation (Phase 10)."""

import uuid

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from okapi_api.core.security import hash_password
from okapi_api.models import Document, User
from okapi_api.repositories.embedding_repository import EmbeddingRepository
from okapi_api.repositories.field_repository import FieldRepository
from okapi_api.services.rag_service import RAGService
from okapi_api.services.versioning_service import VersioningService

pytestmark = pytest.mark.integration


def test_cross_document_vector_isolation(engine: Engine) -> None:
    """Proves that vector similarity search strictly isolates document boundaries."""
    with Session(engine) as session:
        # Create Owner A and Owner B
        user_a = User(
            email=f"doctor-a-{uuid.uuid4()}@okapi.dev",
            full_name="Dr. Alpha",
            role="clinician",
            password_hash=hash_password("pass"),
            attributes={"clearance_level": 3, "department": "oncology"},
        )
        user_b = User(
            email=f"doctor-b-{uuid.uuid4()}@okapi.dev",
            full_name="Dr. Beta",
            role="clinician",
            password_hash=hash_password("pass"),
            attributes={"clearance_level": 3, "department": "cardiology"},
        )
        session.add_all([user_a, user_b])
        session.flush()

        # Document A: Oncology Patient
        doc_a = Document(title="Patient Alpha EHR", doc_type="record", created_by=user_a.id)
        # Document B: Cardiology Patient
        doc_b = Document(title="Patient Beta EHR", doc_type="record", created_by=user_b.id)
        session.add_all([doc_a, doc_b])
        session.flush()

        field_repo = FieldRepository(session)
        version_service = VersioningService(field_repo)
        embedding_repo = EmbeddingRepository(session)
        rag_service = RAGService(fields=field_repo, embeddings=embedding_repo)

        # Field in Doc A: Highly relevant to brain tumor
        field_a = field_repo.register_field(document_id=doc_a.id, field_key="patient.diagnosis")
        version_service.create_version(
            field_id=field_a.id,
            new_value="Stage 4 Glioblastoma Multiforme in frontal lobe",
            actor_id=user_a.id,
            parent_ids=[],
        )

        # Field in Doc B: Unrelated hypertension
        field_b = field_repo.register_field(document_id=doc_b.id, field_key="patient.diagnosis")
        version_service.create_version(
            field_id=field_b.id,
            new_value="Essential Hypertension 135/85 mmHg",
            actor_id=user_b.id,
            parent_ids=[],
        )
        session.commit()

        # Attacker/Clinician queries Document B with oncology tumor terms
        # Document A's embedding has maximum semantic similarity, but must NEVER leak into Doc B
        rag_result = rag_service.retrieve(
            document_id=doc_b.id,
            allowed_field_keys=["patient.diagnosis"],
            question="What type of brain cancer or glioblastoma tumor does this patient have?",
        )

        # Result MUST contain Doc B's hypertension data and 0% of Doc A's tumor data
        assert "Glioblastoma" not in rag_result["answer"]
        assert "frontal lobe" not in rag_result["answer"]
        assert "Hypertension" in rag_result["fields"]["patient.diagnosis"]
        assert "Glioblastoma" not in str(rag_result["fields"])
