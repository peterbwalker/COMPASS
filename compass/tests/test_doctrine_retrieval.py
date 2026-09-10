from src.doctrine.corpus import DoctrineChunk
from src.doctrine.retrieval import DoctrineRetriever


def test_retriever_empty_corpus_returns_nothing():
    retriever = DoctrineRetriever(chunks=[])
    assert retriever.is_empty
    assert retriever.retrieve("anything", k=3) == []


def test_retriever_returns_most_relevant_chunk_first():
    chunks = [
        DoctrineChunk(source="fuel_doctrine.txt", chunk_id=0,
                      text="Bulk petroleum distribution requires forward staging of fuel reserves."),
        DoctrineChunk(source="medical_doctrine.txt", chunk_id=0,
                      text="Health service support includes casualty evacuation and forward resuscitative care."),
        DoctrineChunk(source="transport_doctrine.txt", chunk_id=0,
                      text="Convoy movement control coordinates routing through contested transportation corridors."),
    ]
    retriever = DoctrineRetriever(chunks)
    assert not retriever.is_empty

    results = retriever.retrieve("fuel petroleum distribution reserves", k=1)

    assert len(results) == 1
    assert results[0].source == "fuel_doctrine.txt"
    assert results[0].score > 0


def test_retriever_respects_k_limit():
    chunks = [
        DoctrineChunk(source="doc.txt", chunk_id=i, text=f"contested logistics passage number {i}")
        for i in range(10)
    ]
    retriever = DoctrineRetriever(chunks)
    results = retriever.retrieve("contested logistics", k=3)
    assert len(results) == 3
