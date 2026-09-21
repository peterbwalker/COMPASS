"""
Doctrine corpus retrieval: BM25 (keyword), embeddings (semantic), and a
hybrid combining both.

BM25 alone is transparent about *why* a passage matched (shared terms)
and needs no GPU/extra model -- good for small corpora and debugging.
Embeddings (see embeddings.py) catch conceptually related passages that
share no vocabulary with the query. get_retriever() below builds a
hybrid combining both when embedding dependencies (sentence-transformers,
torch) are available, and falls back to BM25-only otherwise -- so this
module works with zero extra setup, and gets better with it.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional

from rank_bm25 import BM25Okapi

from src.doctrine.corpus import DoctrineChunk, load_corpus


@dataclass
class RetrievedPassage:
    source: str
    text: str
    score: float


class DoctrineRetriever:
    """BM25 keyword retrieval."""

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


class HybridDoctrineRetriever:
    """
    Combines a BM25 retriever and an embedding retriever via Reciprocal
    Rank Fusion (RRF): each retriever's *rank* (not raw score) for a
    chunk contributes 1/(rrf_k + rank) to that chunk's fused score, then
    results are re-sorted by the summed score. RRF is used specifically
    because BM25 and cosine-similarity scores live on totally different,
    non-comparable scales -- fusing on rank sidesteps having to
    normalize or weight two incompatible score distributions.

    Exposes the same .retrieve(query, k) / .is_empty interface as
    DoctrineRetriever, so it's a drop-in replacement anywhere a plain
    retriever is used.
    """

    def __init__(self, bm25_retriever: DoctrineRetriever, embedding_retriever, rrf_k: int = 60):
        self._bm25 = bm25_retriever
        self._embed = embedding_retriever
        self._rrf_k = rrf_k

    @property
    def is_empty(self) -> bool:
        return self._bm25.is_empty and self._embed.is_empty

    def retrieve(self, query: str, k: int = 3, candidate_pool: int = 10) -> List[RetrievedPassage]:
        """
        `candidate_pool` controls how many results each underlying
        retriever contributes before fusion -- wider than the final `k`
        so a passage ranked, say, 4th by BM25 but 1st by embeddings
        still gets a chance to fuse to the top.
        """
        if self.is_empty:
            return []

        bm25_results = self._bm25.retrieve(query, k=candidate_pool) if not self._bm25.is_empty else []
        embed_results = self._embed.retrieve(query, k=candidate_pool) if not self._embed.is_empty else []

        fused_scores: Dict[str, float] = {}
        passage_by_key: Dict[str, RetrievedPassage] = {}

        for rank, passage in enumerate(bm25_results):
            key = f"{passage.source}:{passage.text[:50]}"
            fused_scores[key] = fused_scores.get(key, 0.0) + 1.0 / (self._rrf_k + rank)
            passage_by_key[key] = passage

        for rank, passage in enumerate(embed_results):
            key = f"{passage.source}:{passage.text[:50]}"
            fused_scores[key] = fused_scores.get(key, 0.0) + 1.0 / (self._rrf_k + rank)
            passage_by_key[key] = passage

        ranked_keys = sorted(fused_scores, key=lambda k_: fused_scores[k_], reverse=True)[:k]
        return [
            RetrievedPassage(
                source=passage_by_key[key].source,
                text=passage_by_key[key].text,
                score=fused_scores[key],
            )
            for key in ranked_keys
        ]


_retriever_singleton = None


def get_retriever(doctrine_dir: str = "doctrine"):
    """
    Lazily load and cache the doctrine corpus for the life of the
    process. Builds a HybridDoctrineRetriever (BM25 + embeddings) if
    `sentence-transformers`/`torch` are installed, otherwise falls back
    to BM25-only automatically -- callers get the same .retrieve()
    interface either way. Call `reset_retriever()` if the doctrine/
    folder's contents change and you need a fresh load without
    restarting the process.
    """
    global _retriever_singleton
    if _retriever_singleton is None:
        chunks = load_corpus(doctrine_dir)
        bm25 = DoctrineRetriever(chunks)

        try:
            from src.doctrine.embeddings import EmbeddingRetriever
            embed = EmbeddingRetriever(chunks)
            _retriever_singleton = HybridDoctrineRetriever(bm25, embed)
        except ImportError:
            # sentence-transformers/torch not installed -- BM25-only.
            _retriever_singleton = bm25

    return _retriever_singleton


def reset_retriever() -> None:
    global _retriever_singleton
    _retriever_singleton = None
