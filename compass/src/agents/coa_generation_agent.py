"""
Course of Action (COA) Generation Agent

Generates candidate reroute/resupply/prioritization options given the
current forecast and threat picture. Intended hybrid pattern: an LLM
proposes/narrates options, a classical solver (optimization or graph
search) checks feasibility and cost. Placeholder generates one naive COA.
"""

from src.orchestrator.state import CompassState, CourseOfAction


def coa_generation_agent(state: CompassState) -> CompassState:
    forecast = state["forecast"]

    coas = []
    for i, shortfall in enumerate(forecast["projected_shortfalls"]):
        coas.append(
            CourseOfAction(
                coa_id=f"COA_{i+1}",
                description=f"Reroute traffic away from {shortfall['route_id']}",
                affected_routes=[shortfall["route_id"]],
                estimated_cost=100.0,
                estimated_risk=0.2,
                rationale="Stub rationale — replace with LLM-generated narrative.",
            )
        )

    if not coas:
        coas.append(
            CourseOfAction(
                coa_id="COA_HOLD",
                description="No shortfalls projected — maintain current plan.",
                affected_routes=[],
                estimated_cost=0.0,
                estimated_risk=0.0,
                rationale="No action required based on current forecast.",
            )
        )

    return {"candidate_coas": coas}
