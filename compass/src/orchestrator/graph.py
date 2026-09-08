"""
COMPASS orchestration graph.

Topology:

    sensing -> threat_assessment -> forecasting -> coa_generation
        -> risk_evaluation -> [HUMAN GATE] -> adjudication -> END
                                    |
                                    +-- replan_requested? -> forecasting

Run directly for a smoke test:  python -m src.orchestrator.graph
"""

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from src.orchestrator.state import CompassState
from src.agents import (
    sensing_agent,
    threat_assessment_agent,
    forecasting_agent,
    coa_generation_agent,
    risk_evaluation_agent,
    adjudication_agent,
)


def route_after_risk_evaluation(state: CompassState) -> str:
    """Decide whether to proceed to adjudication or loop back to replan."""
    if state.get("replan_requested"):
        return "forecasting"
    return "adjudication"


def build_graph():
    graph = StateGraph(CompassState)

    graph.add_node("sensing", sensing_agent)
    graph.add_node("threat_assessment", threat_assessment_agent)
    graph.add_node("forecasting", forecasting_agent)
    graph.add_node("coa_generation", coa_generation_agent)
    graph.add_node("risk_evaluation", risk_evaluation_agent)
    graph.add_node("adjudication", adjudication_agent)

    graph.set_entry_point("sensing")
    graph.add_edge("sensing", "threat_assessment")
    graph.add_edge("threat_assessment", "forecasting")
    graph.add_edge("forecasting", "coa_generation")
    graph.add_edge("coa_generation", "risk_evaluation")

    # Conditional edge: supports a replan loop before the human gate.
    graph.add_conditional_edges(
        "risk_evaluation",
        route_after_risk_evaluation,
        {"forecasting": "forecasting", "adjudication": "adjudication"},
    )

    graph.add_edge("adjudication", END)

    # `interrupt_before` pauses execution before adjudication so a human
    # can review candidate_coas + risk_evaluations before a decision is
    # recorded. Requires a checkpointer (MemorySaver here; swap for a
    # persistent one in production).
    checkpointer = MemorySaver()
    return graph.compile(checkpointer=checkpointer, interrupt_before=["adjudication"])


if __name__ == "__main__":
    app = build_graph()

    initial_state: CompassState = {
        "raw_feeds": [],
        "replan_requested": False,
        "iteration": 0,
    }

    config = {"configurable": {"thread_id": "smoke-test-1"}}

    # First invoke runs sensing -> risk_evaluation, then pauses (human gate).
    result = app.invoke(initial_state, config=config)
    print("Paused before adjudication. State so far:")
    print(result)

    # Resume to simulate human approval and complete the run.
    final = app.invoke(None, config=config)
    print("\nFinal state after adjudication:")
    print(final)
