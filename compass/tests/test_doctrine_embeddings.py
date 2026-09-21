"""
Tests for EmbeddingRetriever using an injected fake encoder -- this
tests the retrieval math (cosine similarity ranking) without requiring
sentence-transformers/torch to be installed or a real model to be
downloaded. On your machine with those installed, the real encoder path
(no encode_fn passed) is what actually runs.
"""

import numpy as np

from src.doctrine.corpus import DoctrineChunk
from src.doctrine.embeddings import EmbeddingRetriever


def _fake_encoder(vectors_by_text):
    """Build a fake encode_fn that returns pre-assigned vectors for
    known texts, so test cases can control similarity deterministically."""
    def encode(texts):
        return np.array([vectors_by_text[t] for t in texts], dtype=np.float32)
    return encode


def test_embedding_retriever_empty_corpus():
    retriever = EmbeddingRetriever(chunks=[], encode_fn=lambda texts: np.zeros((len(texts), 4)))
    assert retriever.is_empty
    assert retriever.retrieve("anything") == []


def test_embedding_retriever_ranks_by_cosine_similarity():
    chunks = [
        DoctrineChunk(source="fuel.txt", chunk_id=0, text="fuel passage"),
        DoctrineChunk(source="medical.txt", chunk_id=0, text="medical passage"),
    ]

    # Unit vectors: fuel closely aligned with the query, medical orthogonal.
    vectors = {
        "fuel passage": np.array([1.0, 0.0]),
        "medical passage": np.array([0.0, 1.0]),
        "query about fuel": np.array([0.9, 0.1]),
    }
    encode_fn = _fake_encoder(vectors)

    retriever = EmbeddingRetriever(chunks=chunks, encode_fn=encode_fn)
    results = retriever.retrieve("query about fuel", k=2)

    assert results[0].source == "fuel.txt"
    assert results[0].score > results[1].score


def test_embedding_retriever_semantic_match_without_shared_words():
    """
    The actual point of embeddings over BM25: a query and a passage with
    ZERO shared vocabulary still match if they're semantically similar
    (simulated here via the fake encoder's assigned vectors).
    """
    chunks = [
        DoctrineChunk(source="petroleum.txt", chunk_id=0, text="petroleum resupply operations"),
        DoctrineChunk(source="unrelated.txt", chunk_id=0, text="personnel administrative records"),
    ]
    vectors = {
        "petroleum resupply operations": np.array([1.0, 0.0]),
        "personnel administrative records": np.array([0.0, 1.0]),
        "fuel replenishment": np.array([0.95, 0.05]),  # no shared words with "petroleum resupply operations"
    }
    encode_fn = _fake_encoder(vectors)

    retriever = EmbeddingRetriever(chunks=chunks, encode_fn=encode_fn)
    results = retriever.retrieve("fuel replenishment", k=1)

    assert results[0].source == "petroleum.txt"


def test_embedding_retriever_respects_k():
    chunks = [
        DoctrineChunk(source=f"doc{i}.txt", chunk_id=0, text=f"passage {i}")
        for i in range(5)
    ]
    vectors = {f"passage {i}": np.array([1.0, i * 0.1]) for i in range(5)}
    vectors["query"] = np.array([1.0, 0.0])
    encode_fn = _fake_encoder(vectors)

    retriever = EmbeddingRetriever(chunks=chunks, encode_fn=encode_fn)
    results = retriever.retrieve("query", k=2)
    assert len(results) == 2
