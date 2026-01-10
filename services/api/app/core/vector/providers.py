from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Protocol


@dataclass(frozen=True)
class Embedding:
    vector: List[float]
    embedding_version: str
    provider: str
    metadata: Dict[str, Any] | None = None


class EmbeddingProvider(Protocol):
    name: str

    def embed_text(self, *, text: str, embedding_version: str) -> Embedding:
        ...


class VectorIndex(Protocol):
    name: str

    def upsert(
        self,
        *,
        namespace: str,
        vectors: Iterable[tuple[str, Embedding]],
        metadata_by_id: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> None:
        ...

    def query(
        self,
        *,
        namespace: str,
        embedding: Embedding,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        ...


class NoopEmbeddingProvider:
    name = "noop"

    def embed_text(self, *, text: str, embedding_version: str) -> Embedding:
        # Deterministic, cheap placeholder (NOT for production semantic search).
        # Keeps the interface stable while vector layer is gated off.
        h = float(sum(ord(c) for c in (text or "")) % 997)
        vec = [h / 997.0]
        return Embedding(vector=vec, embedding_version=embedding_version, provider=self.name)


class NoopVectorIndex:
    name = "noop"

    def upsert(
        self,
        *,
        namespace: str,
        vectors: Iterable[tuple[str, Embedding]],
        metadata_by_id: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> None:
        return

    def query(
        self,
        *,
        namespace: str,
        embedding: Embedding,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        return []
