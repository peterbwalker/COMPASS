"""
Predictive / Forecasting Agent

Projects future logistics network state given current snapshot + threat
assessment. This is the best candidate for a real trained model (time
series / graph-based ETA & risk prediction) — prototype it in
notebooks/ before promoting here.
"""

from src.orchestrator.state import CompassState, Forecast


def forecasting_agent(state: CompassState) -> CompassState:
    snapshot = state["logistics_snapshot"]
    threat = state["threat_assessment"]

    shortfalls = []
    for route_id, prob in threat["denial_probability"].items():
        if prob > 0.5:
            shortfalls.append({"route_id": route_id, "risk": "high"})

    forecast = Forecast(
        horizon_hours=24,
        projected_throughput={r["id"]: 1.0 for r in snapshot["routes"]},
        projected_shortfalls=shortfalls,
    )
    return {"forecast": forecast}
