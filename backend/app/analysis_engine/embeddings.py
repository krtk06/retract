"""Embedding providers for the RAG index.

Canonical dimension is 384 across providers so the vector column is stable:
- fastembed: local ONNX model (BAAI/bge-small-en-v1.5), no torch, works offline
- openai: text-embedding-3-small with dimensions=384
- hashing: deterministic token-hashing fallback (tests / no-network CI)
"""

import hashlib
import math
import re
from collections.abc import Sequence
from typing import Protocol

from app.config import get_settings
from app.models import EMBEDDING_DIM

_TOKEN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|\d+")


class EmbeddingProvider(Protocol):
    name: str
    dim: int

    def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


class HashingEmbeddingProvider:
    """Deterministic bag-of-tokens hashing vectorizer with sublinear TF.

    Not as good as a trained model, but requires no network/model and gives
    stable, comparable vectors — used in tests and as an offline fallback.
    """

    name = "hashing"
    dim = EMBEDDING_DIM

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        vector = [0.0] * self.dim
        counts: dict[int, int] = {}
        for token in _TOKEN.findall(text.lower()):
            digest = int.from_bytes(hashlib.blake2b(token.encode(), digest_size=4).digest(), "big")
            counts[digest % self.dim] = counts.get(digest % self.dim, 0) + 1
        for index, count in counts.items():
            vector[index] = 1.0 + math.log(count)
        norm = math.sqrt(sum(v * v for v in vector)) or 1.0
        return [v / norm for v in vector]


class FastEmbedProvider:
    name = "fastembed"
    dim = EMBEDDING_DIM

    def __init__(self, model_name: str) -> None:
        from fastembed import TextEmbedding

        self._model = TextEmbedding(model_name)

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [list(map(float, vector)) for vector in self._model.embed(list(texts))]


class OpenAIEmbeddingProvider:
    name = "openai"
    dim = EMBEDDING_DIM

    def __init__(self, api_key: str, model_name: str) -> None:
        import httpx

        self._api_key = api_key
        self._model_name = model_name
        self._client = httpx.Client(timeout=60.0)

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        response = self._client.post(
            "https://api.openai.com/v1/embeddings",
            headers={"Authorization": f"Bearer {self._api_key}"},
            json={
                "model": self._model_name,
                "input": list(texts),
                "dimensions": self.dim,
            },
        )
        response.raise_for_status()
        data = response.json()["data"]
        return [item["embedding"] for item in data]


_provider: EmbeddingProvider | None = None


def get_embedding_provider() -> EmbeddingProvider:
    global _provider
    if _provider is None:
        _provider = _build_provider()
    return _provider


def set_embedding_provider(provider: EmbeddingProvider | None) -> None:
    """Test helper."""
    global _provider
    _provider = provider


def _build_provider() -> EmbeddingProvider:
    settings = get_settings()
    provider = settings.embedding_provider.lower()
    if provider == "fastembed":
        try:
            return FastEmbedProvider(settings.embedding_model)
        except Exception:  # noqa: BLE001 — fall back rather than break analysis
            return HashingEmbeddingProvider()
    if provider == "openai":
        if not settings.openai_api_key:
            raise RuntimeError("AI_INTEL_OPENAI_API_KEY is required for the openai provider")
        return OpenAIEmbeddingProvider(settings.openai_api_key, settings.openai_embedding_model)
    return HashingEmbeddingProvider()


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    norm_a = math.sqrt(sum(x * x for x in a)) or 1.0
    norm_b = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (norm_a * norm_b)
