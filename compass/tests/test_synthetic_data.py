from itertools import groupby

from src.utils.synthetic_data import ScenarioConfig, generate_scenario


def test_generate_scenario_shapes():
    config = ScenarioConfig(
        num_ports=1, num_depots=2, num_forward_areas=3,
        horizon_hours=24, timestep_hours=6,
    )
    scenario = generate_scenario(config)

    expected_nodes = config.num_ports + config.num_depots + config.num_forward_areas
    expected_steps = config.horizon_hours // config.timestep_hours

    assert len(scenario["nodes"]) == expected_nodes
    assert len(scenario["snapshots"]) == expected_steps
    assert len(scenario["ground_truth_denials"]) == expected_steps

    # Every route in the topology should have a denial entry each step
    route_ids = {r["id"] for r in scenario["routes"]}
    for denials in scenario["ground_truth_denials"]:
        assert set(denials.keys()) == route_ids


def test_generate_scenario_is_deterministic_with_seed():
    config = ScenarioConfig(seed=7, horizon_hours=12, timestep_hours=6)
    a = generate_scenario(config)
    b = generate_scenario(config)
    assert a["ground_truth_denials"] == b["ground_truth_denials"]


def test_contested_episodes_persist_for_configured_duration():
    """
    With contested_duration_range fixed to a single value (3, 3), every
    contested run should be a multiple of 3 steps -- checked directly
    against the run-length structure of the generated data, not just
    aggregate statistics that could pass by coincidence. (Adjacent
    episodes can legitimately merge into one longer run if a new episode
    triggers on the same step the previous one ends; the only run
    excluded from the multiple-of-3 check is the final one, since it may
    be truncated by the end of the scenario mid-episode.)
    """
    config = ScenarioConfig(
        num_ports=1, num_depots=1, num_forward_areas=0,
        horizon_hours=600, timestep_hours=6,  # 100 steps, several full episodes
        threat_spike_probability=0.3,
        contested_duration_range=(3, 3),
        seed=1,
    )
    scenario = generate_scenario(config)
    route_id = scenario["routes"][0]["id"]

    contested_flags = [
        step["threat_spike"]
        for snap in scenario["snapshots"]
        for step in snap["routes"]
        if step["id"] == route_id
    ]

    runs = []
    idx = 0
    for value, group in groupby(contested_flags):
        length = len(list(group))
        runs.append((value, idx, length))
        idx += length

    true_runs = [(start, length) for value, start, length in runs if value]
    assert len(true_runs) >= 2, "expected multiple contested episodes over this horizon"

    last_index = len(contested_flags) - 1
    # Exclude the final run -- it may be truncated by the scenario ending
    # mid-episode, so it isn't required to be a clean multiple of 3.
    checkable_runs = [
        (start, length) for start, length in true_runs
        if (start + length - 1) != last_index
    ]
    assert len(checkable_runs) > 0
    for _, length in checkable_runs:
        assert length % 3 == 0
