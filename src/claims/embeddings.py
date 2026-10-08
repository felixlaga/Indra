"""Optional sentence embeddings for semantic evidence retrieval.

Disabled unless ``INDRA_EMBEDDING_MODEL`` names a Hugging Face sentence-embedding
model (for example ``sentence-transformers/all-MiniLM-L6-v2``). The model is
downloaded on first use into the Hugging Face cache and runs locally on CPU.
Embeddings only nominate passages for the verifier; they never judge support.
"""

from __future__ import annotations

import logging
import math
import os
from threading import Lock
from typing import Protocol, Sequence

logger = logging.getLogger(__name__)
EMBEDDING_MODEL_ENV = "INDRA_EMBEDDING_MODEL"
MAX_TOKENS = 256
BATCH_SIZE = 32


class Embedder(Protocol):
    name: str

    def embed(self, texts: Sequence[str]) -> list[tuple[float, ...]]: ...


def unit(vector: Sequence[float]) -> tuple[float, ...]:
    norm = math.sqrt(sum(v * v for v in vector)) or 1.0
    return tuple(v / norm for v in vector)


class LocalEmbedder:
    """Mean-pooled transformer embeddings, normalized to unit length."""

    def __init__(self, name: str):
        self.name = name
        self._model = self._tokenizer = None
        self._lock = Lock()

    def _load(self):
        with self._lock:
            if self._model is None:
                from transformers import AutoModel, AutoTokenizer

                logger.info("Loading embedding model %s", self.name)
                self._tokenizer = AutoTokenizer.from_pretrained(self.name)
                self._model = AutoModel.from_pretrained(self.name).eval()
        return self._tokenizer, self._model

    def embed(self, texts: Sequence[str]) -> list[tuple[float, ...]]:
        import torch

        tokenizer, model = self._load()
        vectors: list[tuple[float, ...]] = []
        for start in range(0, len(texts), BATCH_SIZE):
            batch = list(texts[start : start + BATCH_SIZE])
            encoded = tokenizer(
                batch,
                padding=True,
                truncation=True,
                max_length=MAX_TOKENS,
                return_tensors="pt",
            )
            with torch.no_grad():
                hidden = model(**encoded).last_hidden_state
            mask = encoded["attention_mask"].unsqueeze(-1).to(hidden.dtype)
            pooled = (hidden * mask).sum(1) / mask.sum(1).clamp(min=1e-9)
            pooled = torch.nn.functional.normalize(pooled, p=2, dim=1)
            vectors.extend(tuple(float(v) for v in row) for row in pooled.tolist())
        return vectors


_cached: dict[str, LocalEmbedder] = {}


def embedder_from_environment() -> Embedder | None:
    """The configured embedder, shared per process, or None when disabled."""

    name = os.getenv(EMBEDDING_MODEL_ENV, "").strip()
    if not name or name.lower() in {"off", "none", "false", "0"}:
        return None
    if name not in _cached:
        _cached[name] = LocalEmbedder(name)
    return _cached[name]
