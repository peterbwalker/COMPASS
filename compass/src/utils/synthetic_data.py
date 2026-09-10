"""
Synthetic contested-logistics scenario generator.

Produces a static node/route topology plus a time series of
LogisticsSnapshots with injected threat events, for prototyping and
testing the forecasting and threat-assessment agents before real data
sources are available.
"""

import random
from dataclasses import dataclass
from typing import Dict, List, Tuple

from src.orchestrator.state import LogisticsSnapshot


@dataclass
class ScenarioConfig:
    num_depots: int = 2
    num_forward_areas: int = 3
    num_ports: int = 1
    horizon_hours: int = 72
    timestep_hours: int = 6
    base_denial_probability: float = 0.05
    threat_spike_probability: float = 0.15
    # Denial probability while a route is in a contested episode. This is
    # deliberately high and fairly deterministic: a route actually being
    # actively denied (route cut, ambush, jamming) is usually reliably
    # unusable, not just "somewhat riskier." Realism here matters --
    # if contested-state denial is only modestly elevated, individual
    # observations stay noisy even though the underlying cause persists,
    # which defeats the point of adding persistence at all.
    contested_denial_probability: float = 0.85
    # Once a route becomes contested, it stays contested for a random
    # number of timesteps in this range (inclusive) rather than resetting
    # independently each step. This gives the data actual temporal
    # structure -- an adversary holding a corridor doesn't usually let go
    # after one timestep -- which a rolling-window model can exploit.
    contested_duration_range: Tuple[int, int] = (2, 5)
    commodities: Tuple[str, ...] = ("fuel", "medical", "ammunition", "food")
    seed: int = 42


def _build_network(config: ScenarioConfig) -> Tuple[List[Dict], List[Dict]]:
    """Create a static node/route topology for the scenario."""
    random.seed(config.seed)

    nodes = []
    for i in range(config.num_ports):
        nodes.append({"id": f"PORT_{i+1}", "type": "port", "status": "operational"})
    for i in range(config.num_depots):
        nodes.append({"id": f"DEPOT_{i+1}", "type": "depot", "status": "operational"})
    for i in range(config.num_forward_areas):
        nodes.append({"id": f"FSA_{i+1}", "type": "forward_staging_area", "status": "operational"})

    routes = []
    route_counter = 1
    ports = [n["id"] for n in nodes if n["type"] == "port"]
    depots = [n["id"] for n in nodes if n["type"] == "depot"]
    fsas = [n["id"] for n in nodes if n["type"] == "forward_staging_area"]

    # Port -> Depot legs (strategic/operational lift)
    for port in ports:
        for depot in depots:
            routes.append({
                "id": f"ROUTE_{route_counter}",
                "from": port,
                "to": depot,
                "capacity": random.randint(500, 1000),
                "base_denial_probability": config.base_denial_probability,
                "status": "open",
            })
            route_counter += 1

    # Depot -> FSA legs (tactical/forward resupply, riskier)
    for i, fsa in enumerate(fsas):
        depot = depots[i % len(depots)]
        routes.append({
            "id": f"ROUTE_{route_counter}",
            "from": depot,
            "to": fsa,
            "capacity": random.randint(100, 300),
            "base_denial_probability": config.base_denial_probability * 1.5,
            "status": "open",
        })
        route_counter += 1

    return nodes, routes


def _initial_inventory(nodes: List[Dict], config: ScenarioConfig) -> Dict[str, Dict[str, float]]:
    inventory = {}
    for node in nodes:
        base = 2000 if node["type"] == "port" else 800 if node["type"] == "depot" else 200
        inventory[node["id"]] = {c: base * random.uniform(0.8, 1.2) for c in config.commodities}
    return inventory


def generate_scenario(config: ScenarioConfig = None) -> Dict:
    """
    Generate a full synthetic scenario: static topology + a time series of
    LogisticsSnapshots with injected threat events and ground-truth labels.

    Returns a dict with:
        - "nodes", "routes": static topology
        - "snapshots": List[LogisticsSnapshot] over time
        - "ground_truth_denials": List[Dict] per-timestep actual route
          denial events (route_id -> bool) -- useful for evaluating a
          forecasting or threat-assessment model against what "actually
          happened" in the synthetic scenario.
    """
    config = config or ScenarioConfig()
    random.seed(config.seed)

    nodes, routes = _build_network(config)
    inventory = _initial_inventory(nodes, config)

    snapshots = []
    ground_truth_denials = []

    # Per-route countdown of remaining contested timesteps. 0 means the
    # route is currently open/uncontested.
    contested_remaining = {route["id"]: 0 for route in routes}

    num_steps = config.horizon_hours // config.timestep_hours
    for step in range(num_steps):
        hour = step * config.timestep_hours
        timestamp = f"2026-01-01T{hour:02d}:00:00Z"

        step_routes = []
        denials_this_step = {}
        for route in routes:
            route_id = route["id"]

            if contested_remaining[route_id] == 0:
                # Not currently contested -- roll for a new contestation
                # episode starting this step.
                if random.random() < config.threat_spike_probability:
                    duration = random.randint(*config.contested_duration_range)
                    contested_remaining[route_id] = duration

            is_contested = contested_remaining[route_id] > 0
            if is_contested:
                denial_prob = config.contested_denial_probability
                contested_remaining[route_id] -= 1
            else:
                denial_prob = route["base_denial_probability"]

            is_denied = random.random() < denial_prob
            denials_this_step[route_id] = is_denied

            step_routes.append({
                **{k: v for k, v in route.items() if k != "base_denial_probability"},
                "status": "closed" if is_denied else "open",
                "threat_spike": is_contested,
            })

        # Simple randomized consumption to give inventory a nontrivial trend
        for node_id in inventory:
            for commodity in config.commodities:
                consumption = random.uniform(5, 20)
                inventory[node_id][commodity] = max(0.0, inventory[node_id][commodity] - consumption)

        snapshots.append(LogisticsSnapshot(
            timestamp=timestamp,
            nodes=nodes,
            routes=step_routes,
            inventory={k: dict(v) for k, v in inventory.items()},
        ))
        ground_truth_denials.append(denials_this_step)

    return {
        "nodes": nodes,
        "routes": routes,
        "snapshots": snapshots,
        "ground_truth_denials": ground_truth_denials,
    }


if __name__ == "__main__":
    scenario = generate_scenario()
    print(
        f"Generated {len(scenario['snapshots'])} snapshots over "
        f"{len(scenario['nodes'])} nodes and {len(scenario['routes'])} routes."
    )
    print("First snapshot:", scenario["snapshots"][0])
    print("First-step ground-truth denials:", scenario["ground_truth_denials"][0])
