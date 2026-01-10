from __future__ import annotations

import os

from app.core.vector.providers import NoopEmbeddingProvider, NoopVectorIndex, EmbeddingProvider, VectorIndex


def get_embedding_provider() -> EmbeddingProvider:
    name = (os.getenv("SAVO_EMBEDDING_PROVIDER") or "noop").strip().lower() or "noop"
    if name == "noop":
        return NoopEmbeddingProvider()
    # Provider implementations are intentionally pluggable; unknown providers fall back to noop.
    return NoopEmbeddingProvider()


def get_vector_index() -> VectorIndex:
    name = (os.getenv("SAVO_VECTOR_DB_PROVIDER") or "noop").strip().lower() or "noop"
    if name == "noop":
        return NoopVectorIndex()
    return NoopVectorIndex()
