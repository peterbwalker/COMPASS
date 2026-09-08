"""
Integration test: verify the COMPASS graph runs end-to-end and pauses
correctly at the human interrupt gate.
"""

from src.orchestrator.graph import build_graph


def test_graph_runs_to_human_gate_and_completes():
    app = build_graph()
    config = {"configurable": {"thread_id": "test-run-1"}}

    initial_state = {
        "raw_feeds": [],
        "replan_requested": False,
        "iteration": 0,
    }

    paused = app.invoke(initial_state, config=config)
    assert "risk_evaluations" in paused
    assert "selected_coa_id" not in paused  # adjudication hasn't run yet

    final = app.invoke(None, config=config)
    assert "selected_coa_id" in final
    assert final["human_decision"] == "approve"
