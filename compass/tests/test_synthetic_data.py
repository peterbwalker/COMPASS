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
