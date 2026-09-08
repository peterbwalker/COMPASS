"""
Adjudication / Human-Interface Agent

Packages the top-ranked recommendation for human review and records the
decision + rationale for the audit trail. In the real system this node
sits behind a LangGraph interrupt so execution pauses for human input.
"""

from src.orchestrator.state import CompassState


def adjudication_agent(state: CompassState) -> CompassState:
    evaluations = state["risk_evaluations"]
    coas = {c["coa_id"]: c for c in state["candidate_coas"]}

    # Stub: pick the lowest-risk COA. Real version presents all options
    # to a human via the interrupt and waits for `human_decision`.
    best = min(evaluations, key=lambda e: e["risk_score"])
    selected = coas[best["coa_id"]]

    return {
        "selected_coa_id": selected["coa_id"],
        "decision_rationale": (
            f"Selected {selected['coa_id']} ({selected['description']}) — "
            f"lowest scored risk ({best['risk_score']})."
        ),
        "human_decision": "approve",  # placeholder until human gate is wired in
    }
