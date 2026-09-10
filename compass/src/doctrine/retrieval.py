"""
BM25-based retrieval over the doctrine corpus.

Keeps retrieval keyword-based (BM25) rather than embedding-based
deliberately: it's transparent about *why* a passage matched (shared
terms, not opaque vector similarity), needs no extra API key or cost,
and is a reasonable starting point for the (currently small) corpus
sizes this pipeline deals with. Revisit if the corpus grows large enough
that semantic-but-no-shared-vocabulary matches start to matter.
"""

from dataclasses import dataclass
from typing import List, Optional

from rank_bm25 import BM25Okapi

from src.doctrine.corpus import DoctrineChunk, load_corpus


@dataclass
class RetrievedPassage:
    source: str
    text: str
    score: float


class DoctrineRetriever:
    def __init__(self, chunks: List[DoctrineChunk]):
        self.chunks = chunks
        self._bm25: Optional[BM25Okapi] = None
        if chunks:
            tokenized = [c.text.lower().split() for c in chunks]
            self._bm25 = BM25Okapi(tokenized)

    @property
    def is_empty(self) -> bool:
        return self._bm25 is None

    def retrieve(self, query: str, k: int = 3, min_score: Optional[float] = None) -> List[RetrievedPassage]:
        """
        Return the top-k chunks for `query`, sorted by BM25 score
        descending. Returns [] if the corpus is empty -- callers should
        treat this as "no doctrine grounding available yet," not an
        error, and fall back to ungrounded generation.

        `min_score` is None by default (no filtering beyond top-k): BM25
        scores can legitimately be zero or negative on small corpora
        (its IDF term goes negative when a query word appears in most or
        all documents, which is common with only a handful of chunks),
        so filtering on an absolute score threshold by default would
        silently drop genuinely-the-most-relevant results. Pass an
        explicit min_score once the corpus is large enough that a
        relevance floor is actually meaningful.
        """
        if self.is_empty:
            return []

        tokenized_query = query.lower().split()
        scores = self._bm25.get_scores(tokenized_query)

        ranked = sorted(zip(self.chunks, scores), key=lambda pair: pair[1], reverse=True)
        results = [
            RetrievedPassage(source=chunk.source, text=chunk.text, score=float(score))
            for chunk, score in ranked[:k]
            if min_score is None or score > min_score
        ]
        return results


_retriever_singleton: Optional[DoctrineRetriever] = None


def get_retriever(doctrine_dir: str = "doctrine") -> DoctrineRetriever:
    """
    Lazily load and cache the doctrine corpus for the life of the
    process. Call `reset_retriever()` if the doctrine/ folder's contents
    change and you need a fresh load without restarting the process
    (e.g. in a long-running Colab session or the FastAPI backend).
    """
    global _retriever_singleton
    if _retriever_singleton is None:
        chunks = load_corpus(doctrine_dir)
        _retriever_singleton = DoctrineRetriever(chunks)
    return _retriever_singleton


def reset_retriever() -> None:
    global _retriever_singleton
    _retriever_singleton = None
