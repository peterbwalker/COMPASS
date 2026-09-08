from src.utils.baselines import (
    rolling_denial_rate,
    rolling_baseline_forecast,
    backtest_rolling_baseline,
)
from src.utils.synthetic_data import ScenarioConfig, generate_scenario


def test_rolling_denial_rate_basic():
    history = [
        {"R1": True, "R2": False},
        {"R1": False, "R2": False},
        {"R1": True, "R2": True},
    ]
    rates = rolling_denial_rate(history, window=3)
    assert rates["R1"] == 2 / 3
    assert rates["R2"] == 1 / 3


def test_rolling_denial_rate_empty_history():
    assert rolling_denial_rate([], window=4) == {}


def test_rolling_baseline_forecast_flags_high_risk_routes():
    history = [{"R1": True}, {"R1": True}, {"R1": True}]
    routes = [{"id": "R1", "capacity": 100}]

    forecast = rolling_baseline_forecast(history, routes, window=3, shortfall_threshold=0.5)

    assert forecast["projected_throughput"]["R1"] == 0.0
    assert len(forecast["projected_shortfalls"]) == 1
    assert forecast["projected_shortfalls"][0]["route_id"] == "R1"
    assert forecast["projected_shortfalls"][0]["risk"] == "high"


def test_backtest_runs_against_synthetic_scenario():
    config = ScenarioConfig(horizon_hours=48, timestep_hours=6, seed=1)
    scenario = generate_scenario(config)

    results = backtest_rolling_baseline(scenario["ground_truth_denials"], window=3)

    assert results["overall"] is not None
    assert 0.0 <= results["overall"] <= 1.0
    for route_score in results["per_route"].values():
        if route_score is not None:
            assert 0.0 <= route_score <= 1.0
