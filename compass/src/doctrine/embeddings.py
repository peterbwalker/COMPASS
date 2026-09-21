"""
Semantic (embedding-based) doctrine retrieval.

Complements the BM25 retriever in retrieval.py: BM25 matches shared
vocabulary, embeddings match shared *meaning* even when the query and
the passage use different words for the same concept (e.g. a query
about "fuel replenishment" matching a passage about "petroleum
resupply"). Combine both via HybridDoctrineRetriever in retrieval.py
rather than picking one.

GPU usage: the encoder is a sentence-embedding model (small -- typically
1-2 GB), not an LLM. It runs comfortably on any single modern GPU;
multi-GPU here would only matter if you're embedding a very large
corpus and want to parallelize batches across devices, which the
default single-device encoder below doesn't attempt. Revisit if your
corpus grows to the point where encoding time (not retrieval time)
becomes the bottleneck.
"""

from dataclasses import dataclass
from typing import Callable, List, Optional

import numpy as np

from src.doctrine.corpus import DoctrineChunk

# A strong general-purpose open embedding model. Swap via model_name if
# you want something else (e.g. a smaller/faster model for iteration,
# or a domain-tuned one later). ~1.3 GB, runs fine on CPU too if no GPU
# is available -- the "GPU acceleration" here is a speedup, not a
# requirement.
DEFAULT_MODEL = "BAAI/bge-large-en-v1.5"


@dataclass
class RetrievedPassage:
    source: str
    text: str
    score: float


EncodeFn = Callable[[List[str]], np.ndarray]


def _default_encoder(model_name: str, device: Optional[str]) -> EncodeFn:
    """
    Lazily imports sentence-transformers/torch only when actually
    needed (not at module import time), so importing this module never
    requires those (heavy) dependencies to be installed -- only
    constructing an EmbeddingRetriever without an injected encode_fn
    does. This also keeps the module trivially testable: pass your own
    encode_fn and none of this ever runs.
    """
    from sentence_transformers import SentenceTransformer
    import torch

    resolved_device = device or ("cuda" if torch.cuda.is_available() else "cpu")
    model = SentenceTransformer(model_name, device=resolved_device)

    def encode(texts: List[str]) -> np.ndarray:
        return model.encode(
            texts,
            normalize_embeddings=True,  # so dot product == cosine similarity
            convert_to_numpy=True,
            batch_size=32,
            show_progress_bar=False,
        )

    return encode


class EmbeddingRetriever:
    def __init__(
        self,
        chunks: List[DoctrineChunk],
        encode_fn: Optional[EncodeFn] = None,
        model_name: str = DEFAULT_MODEL,
        device: Optional[str] = None,
    ):
        """
        Args:
            chunks: the doctrine corpus to index.
            encode_fn: inject a custom encoder (e.g. a fake one for
                tests, or a different embedding backend). If omitted,
                lazily loads a real sentence-transformers model on
                first use -- requires `sentence-transformers` and
                `torch` to be installed.
            model_name: HuggingFace model id, only used if encode_fn is
                not provided.
            device: "cuda" or "cpu"; auto-detected if not provided
                (only relevant when encode_fn is not provided).
        """
        self.chunks = chunks
        self._encode_fn = encode_fn
        self._model_name = model_name
        self._device = device
        self._embeddings: Optional[np.ndarray] = None

        if chunks:
            self._embeddings = self._encode([c.text for c in chunks])

    def _encode(self, texts: List[str]) -> np.ndarray:
        if self._encode_fn is None:
            self._encode_fn = _default_encoder(self._model_name, self._device)
        return self._encode_fn(texts)

    @property
    def is_empty(self) -> bool:
        return self._embeddings is None or len(self.chunks) == 0

    def retrieve(self, query: str, k: int = 3, min_score: Optional[float] = None) -> List[RetrievedPassage]:
        if self.is_empty:
            return []

        query_vec = self._encode([query])[0]
        # Embeddings are normalized (unit length), so dot product IS cosine similarity.
        scores = self._embeddings @ query_vec

        ranked_idx = np.argsort(-scores)[:k]
        results = []
        for idx in ranked_idx:
            score = float(scores[idx])
            if min_score is not None and score <= min_score:
                continue
            chunk = self.chunks[idx]
            results.append(RetrievedPassage(source=chunk.source, text=chunk.text, score=score))
        return results
