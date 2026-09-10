from src.agents.sensing_agent import sensing_agent
from src.utils.synthetic_data import ScenarioConfig, generate_scenario


def test_sensing_agent_stub_mode_unchanged():
    """Original behavior (raw_feeds as a plain list) still works."""
    result = sensing_agent({"raw_feeds": []})
    assert result["logistics_snapshot"]["nodes"][0]["id"] == "DEPOT_A"
    assert result["denial_history"] == []


def test_sensing_agent_scenario_replay_mode():
    config = ScenarioConfig(horizon_hours=60, timestep_hours=6, seed=1)  # 10 steps
    scenario = generate_scenario(config)

    step = 5
    state = {"raw_feeds": {"scenario": scenario, "current_step": step}}
    result = sensing_agent(state)

    assert result["logistics_snapshot"] == scenario["snapshots"][step]
    assert result["denial_history"] == scenario["ground_truth_denials"][:step]
    # No leakage: history must not include the current or future steps
    assert len(result["denial_history"]) == step
