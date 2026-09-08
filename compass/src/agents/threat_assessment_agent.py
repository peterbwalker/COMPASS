"""
Threat / Contestation Assessment Agent

Interprets adversary activity affecting logistics nodes/routes and produces
denial-probability estimates. Placeholder logic assigns a flat probability;
replace with a real model (e.g. fused ISR/EW reporting, historical denial
base rates, or a learned classifier).
"""

from src.orchestrator.state import CompassState, ThreatAssessment


def threat_assessment_agent(state: CompassState) -> CompassState:
    snapshot = state["logistics_snapshot"]
    route_ids = [r["id"] for r in snapshot["routes"]]

    assessment = ThreatAssessment(
        contested_nodes=[],
        contested_routes=route_ids[:1],  # stub: flag first route as contested
        denial_probability={rid: 0.3 for rid in route_ids},
        confidence=0.5,
    )
    return {"threat_assessment": assessment}
