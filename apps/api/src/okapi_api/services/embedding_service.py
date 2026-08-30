"""Embedding Service — generates normalized dense vectors and calculates cosine similarity.

Deterministic, normalized vector embeddings enable field-level vector indexing and
semantic retrieval without external bottlenecks (architecture doc section 8).
"""

import hashlib
import math
import re
from collections.abc import Sequence

DEFAULT_EMBEDDING_DIM = 384
DEFAULT_MODEL_NAME = "okapi-embed-v1"


class EmbeddingService:
    def __init__(
        self, dim: int = DEFAULT_EMBEDDING_DIM, model_name: str = DEFAULT_MODEL_NAME
    ) -> None:
        self.dim = dim
        self.model_name = model_name

    def embed_text(self, text: str) -> list[float]:
        """Generate a deterministic, L2-normalized dense embedding vector from input text."""
        cleaned = text.strip().lower()
        if not cleaned:
            return [0.0] * self.dim

        # Tokenize words to preserve semantic token frequency
        tokens = re.findall(r"\w+", cleaned)
        if not tokens:
            tokens = [cleaned]

        vector = [0.0] * self.dim
        for token in tokens:
            # Hash token to spread across dimensions deterministically
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            for i in range(min(len(digest), self.dim)):
                # Map byte 0..255 to -1.0 .. 1.0
                val = (digest[i] - 128.0) / 128.0
                idx = (i * 13) % self.dim
                vector[idx] += val

        # Compute L2 norm
        norm_sq = sum(x * x for x in vector)
        if norm_sq == 0.0:
            return [0.0] * self.dim

        norm = math.sqrt(norm_sq)
        return [round(x / norm, 6) for x in vector]

    @staticmethod
    def cosine_similarity(vec_a: Sequence[float], vec_b: Sequence[float]) -> float:
        """Compute cosine similarity between two dense vectors."""
        if len(vec_a) != len(vec_b) or not vec_a:
            return 0.0

        dot_product = sum(a * b for a, b in zip(vec_a, vec_b, strict=False))
        norm_a = math.sqrt(sum(a * a for a in vec_a))
        norm_b = math.sqrt(sum(b * b for b in vec_b))

        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0

        similarity = dot_product / (norm_a * norm_b)
        # Clamp to [-1.0, 1.0] to guard against floating-point precision error
        return max(-1.0, min(1.0, float(similarity)))
