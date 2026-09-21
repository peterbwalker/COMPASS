from src.doctrine.corpus import DoctrineChunk
from src.doctrine.embeddings import EmbeddingRetriever
from src.doctrine.retrieval import DoctrineRetriever, HybridDoctrineRetriever
import numpy as np


def _fake_encoder(vectors_by_text):
    def encode(texts):
        return np.array([vectors_by_text[t] for t in texts], dtype=np.float32)
    return encode


def test_hybrid_empty_when_both_empty():
    bm25 = DoctrineRetriever(chunks=[])
    embed = EmbeddingRetriever(chunks=[], encode_fn=lambda t: np.zeros((len(t), 2)))
    hybrid = HybridDoctrineRetriever(bm25, embed)
    assert hybrid.is_empty
    assert hybrid.retrieve("anything") == []


def test_hybrid_surfaces_result_both_retrievers_agree_on():
    chunks = [
        DoctrineChunk(source="fuel.txt", chunk_id=0, text="fuel petroleum distribution logistics"),
        DoctrineChunk(source="other.txt", chunk_id=0, text="unrelated administrative topic here"),
    ]
    bm25 = DoctrineRetriever(chunks)

    vectors = {
        "fuel petroleum distribution logistics": np.array([1.0, 0.0]),
        "unrelated administrative topic here": np.array([0.0, 1.0]),
        "fuel petroleum": np.array([1.0, 0.0]),
    }
    embed = EmbeddingRetriever(chunks=chunks, encode_fn=_fake_encoder(vectors))

    hybrid = HybridDoctrineRetriever(bm25, embed)
    results = hybrid.retrieve("fuel petroleum", k=1)

    assert results[0].source == "fuel.txt"


def test_hybrid_falls_back_to_single_retriever_if_other_is_empty():
    """If the embedding retriever has no corpus (e.g. deps not
    installed and it's constructed with empty chunks), hybrid should
    still work using just BM25 results."""
    chunks = [DoctrineChunk(source="doc.txt", chunk_id=0, text="contested logistics sustainment")]
    bm25 = DoctrineRetriever(chunks)
    embed = EmbeddingRetriever(chunks=[], encode_fn=lambda t: np.zeros((len(t), 2)))

    hybrid = HybridDoctrineRetriever(bm25, embed)
    results = hybrid.retrieve("contested logistics", k=1)

    assert len(results) == 1
    assert results[0].source == "doc.txt"
