"""Unit tests for EmbeddingService vector normalization and cosine similarity."""

import math

from okapi_api.services.embedding_service import EmbeddingService


def test_embed_text_dimensions_and_normalization() -> None:
    service = EmbeddingService(dim=384)
    vector = service.embed_text("Essential Stage 2 Hypertension")
    assert len(vector) == 384
    norm = math.sqrt(sum(x * x for x in vector))
    assert math.isclose(norm, 1.0, rel_tol=1e-3)


def test_embed_identical_text_is_deterministic() -> None:
    service = EmbeddingService(dim=384)
    v1 = service.embed_text("Metoprolol 50mg daily")
    v2 = service.embed_text("Metoprolol 50mg daily")
    assert v1 == v2


def test_cosine_similarity_identical_vectors() -> None:
    service = EmbeddingService(dim=384)
    v1 = service.embed_text("Type 2 Diabetes Mellitus")
    sim = service.cosine_similarity(v1, v1)
    assert math.isclose(sim, 1.0, rel_tol=1e-4)


def test_cosine_similarity_empty_vectors() -> None:
    service = EmbeddingService(dim=384)
    v1 = [0.0] * 384
    v2 = service.embed_text("Sample Text")
    assert service.cosine_similarity(v1, v2) == 0.0


def test_semantic_similarity_ranking() -> None:
    service = EmbeddingService(dim=384)
    query = service.embed_text("hypertension blood pressure")
    relevant = service.embed_text("patient diagnosed with stage 2 hypertension")
    unrelated = service.embed_text("galaxy cluster astrophysics redshift")

    sim_relevant = service.cosine_similarity(query, relevant)
    sim_unrelated = service.cosine_similarity(query, unrelated)

    assert sim_relevant > sim_unrelated
