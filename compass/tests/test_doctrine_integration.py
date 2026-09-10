"""
Verifies the doctrine-grounding wiring in coa_generation_agent: that
retrieved passages actually make it into the prompt sent to the LLM, and
that the agent still works correctly with an empty corpus (the state
every new user starts in before populating doctrine/).
"""

import importlib

import src.doctrine.retrieval as retrieval_mod
from src.doctrine.corpus import DoctrineChunk
from src.doctrine.retrieval import DoctrineRetriever

coa_mod = importlib.import_module("src.agents.coa_generation_agent")


def test_coa_prompt_includes_retrieved_doctrine_passages(monkeypatch):
    fake_retriever = DoctrineRetriever(chunks=[
        DoctrineChunk(
            source="test_fixture_doctrine.txt", chunk_id=0,
            text="Sustainment planners should preposition reserve stocks along "
                 "alternate routes when primary corridors face contested denial.",
        )
    ])
    monkeypatch.setattr(coa_mod, "get_retriever", lambda: fake_retriever)

    captured_prompt = {}

    def fake_call_claude(prompt, system=None, **kwargs):
        captured_prompt["prompt"] = prompt
        return '[{"description": "Test COA", "affected_routes": [], "estimated_cost": 1.0, "estimated_risk": 0.1, "rationale": "test"}]'

    monkeypatch.setattr(coa_mod, "call_claude", fake_call_claude)

    state = {
        "forecast": {
            "horizon_hours": 24,
            "projected_throughput": {"ROUTE_1": 0.0},
            "projected_shortfalls": [{"route_id": "ROUTE_1", "risk": "high"}],
        }
    }
    coa_mod.coa_generation_agent(state)

    assert "test_fixture_doctrine.txt" in captured_prompt["prompt"]
    assert "preposition reserve stocks" in captured_prompt["prompt"]


def test_coa_generation_unaffected_by_empty_doctrine_corpus(monkeypatch):
    empty_retriever = DoctrineRetriever(chunks=[])
    monkeypatch.setattr(coa_mod, "get_retriever", lambda: empty_retriever)

    captured_prompt = {}

    def fake_call_claude(prompt, system=None, **kwargs):
        captured_prompt["prompt"] = prompt
        return '[{"description": "Test COA", "affected_routes": [], "estimated_cost": 1.0, "estimated_risk": 0.1, "rationale": "test"}]'

    monkeypatch.setattr(coa_mod, "call_claude", fake_call_claude)

    state = {
        "forecast": {
            "horizon_hours": 24,
            "projected_throughput": {"ROUTE_1": 0.0},
            "projected_shortfalls": [{"route_id": "ROUTE_1", "risk": "high"}],
        }
    }
    result = coa_mod.coa_generation_agent(state)

    assert "Relevant doctrine excerpts" not in captured_prompt["prompt"]
    assert len(result["candidate_coas"]) == 1
