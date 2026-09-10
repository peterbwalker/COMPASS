from src.agents.forecasting_agent import forecasting_agent
from src.utils.synthetic_data import ScenarioConfig, generate_scenario


def test_forecasting_agent_falls_back_with_insufficient_history():
    state = {
        "denial_history": [{"ROUTE_1": True}],  # only 1 observation, below threshold
        "threat_assessment": {
            "contested_nodes": [],
            "contested_routes": ["ROUTE_1"],
            "denial_probability": {"ROUTE_1": 0.9},
            "confidence": 0.5,
        },
        "logistics_snapshot": {
            "timestamp": "t",
            "nodes": [],
            "routes": [{"id": "ROUTE_1", "capacity": 100}],
            "inventory": {},
        },
    }
    result = forecasting_agent(state)
    # Fallback path: driven by threat_assessment's denial_probability > 0.5
    assert result["forecast"]["projected_shortfalls"][0]["route_id"] == "ROUTE_1"


def test_forecasting_agent_uses_rolling_model_with_sufficient_history():
    """
    Feed a route with a clearly sustained contested history (mostly
    denied recently) and confirm the rolling-baseline model flags it as
    a shortfall -- this is the real integration point, not the fallback.
    """
    history = [
        {"ROUTE_1": False}, {"ROUTE_1": False},
        {"ROUTE_1": True}, {"ROUTE_1": True}, {"ROUTE_1": True},
    ]
    state = {
        "denial_history": history,
        "logistics_snapshot": {
            "timestamp": "t",
            "nodes": [],
            "routes": [{"id": "ROUTE_1", "capacity": 100}],
            "inventory": {},
        },
    }
    result = forecasting_agent(state)
    shortfall_route_ids = [s["route_id"] for s in result["forecast"]["projected_shortfalls"]]
    assert "ROUTE_1" in shortfall_route_ids


def test_forecasting_agent_against_real_synthetic_scenario():
    """
    End-to-end sanity check against the actual synthetic data generator
    rather than a hand-built history, at a step deep enough to have real
    accumulated history.
    """
    config = ScenarioConfig(horizon_hours=120, timestep_hours=6, seed=1)  # 20 steps
    scenario = generate_scenario(config)
    step = 15

    state = {
        "denial_history": scenario["ground_truth_denials"][:step],
        "logistics_snapshot": scenario["snapshots"][step],
    }
    result = forecasting_agent(state)

    # Just confirm it runs and produces a well-formed Forecast -- whether
    # a shortfall is flagged at this specific step depends on the random
    # scenario, not something to hardcode an assertion against.
    forecast = result["forecast"]
    assert forecast["horizon_hours"] == 24
    assert set(forecast["projected_throughput"].keys()) == {
        r["id"] for r in scenario["snapshots"][step]["routes"]
    }
