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


def test_shrinkage_pulls_estimate_toward_prior():
    # 2 observations, both True -> raw average is 1.0
    history = [{"R1": True}, {"R1": True}]

    no_shrinkage = rolling_denial_rate(history, window=2, shrinkage_k=0.0)
    assert no_shrinkage["R1"] == 1.0

    shrunk = rolling_denial_rate(history, window=2, shrinkage_k=4.0, shrinkage_prior=0.2)
    # (2*1 + 4*0.2) / (2 + 4) = 2.8 / 6
    assert abs(shrunk["R1"] - (2.8 / 6)) < 1e-9
    assert shrunk["R1"] < no_shrinkage["R1"]
    assert shrunk["R1"] > 0.2  # still pulled toward but not all the way to the prior


def test_shrinkage_improves_calibration_on_persistent_synthetic_data():
    """
    Reproduces the actual finding from prototyping: on data with a
    persistent (bursty) contested state, a heavily-smoothed short-window
    estimate beats both the raw rolling average and the flat base-rate
    guess on Brier score. This isn't a tautology -- it's checked against
    real generated data, so it'll catch a regression if the generator or
    the shrinkage math changes in a way that breaks the effect.
    """
    config = ScenarioConfig(horizon_hours=240, timestep_hours=6, seed=1)
    scenario = generate_scenario(config)
    denials = scenario["ground_truth_denials"]

    all_obs = [v for step in denials for v in step.values()]
    base_rate = sum(all_obs) / len(all_obs)
    flat_brier = base_rate * (1 - base_rate)

    raw = backtest_rolling_baseline(denials, window=2)
    shrunk = backtest_rolling_baseline(denials, window=2, shrinkage_k=4.0, shrinkage_prior=base_rate)

    assert shrunk["overall"] < flat_brier
    assert shrunk["overall"] < raw["overall"]


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
