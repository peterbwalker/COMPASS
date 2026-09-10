from unittest.mock import patch

from fastapi.testclient import TestClient


def _fake_call_claude(prompt, system=None, max_tokens=1024, **kwargs):
    if system and "tradeoff" in system.lower():
        return "Fake tradeoff summary."
    return (
        '[{"description": "Fake COA", "affected_routes": ["ROUTE_1"], '
        '"estimated_cost": 40.0, "estimated_risk": 0.3, "rationale": "Fake reason."}]'
    )


def test_get_scenario_returns_topology_with_coordinates():
    from src.api.app import app, _scenario

    client = TestClient(app)
    response = client.get("/api/scenario")

    assert response.status_code == 200
    data = response.json()
    assert data["num_steps"] == len(_scenario["snapshots"])
    assert len(data["nodes"]) == len(_scenario["nodes"])
    for node in data["nodes"]:
        assert "lat" in node and "lon" in node


def test_run_step_returns_full_pipeline_result():
    with patch("src.agents.coa_generation_agent.call_claude", side_effect=_fake_call_claude), \
         patch("src.agents.risk_evaluation_agent.call_claude", side_effect=_fake_call_claude):
        from src.api.app import app

        client = TestClient(app)
        response = client.post("/api/step", json={"step": 20})

        assert response.status_code == 200
        data = response.json()
        assert "candidate_coas" in data
        assert "risk_evaluations" in data
        assert "decision_rationale" in data
        assert data["step"] == 20


def test_run_step_rejects_out_of_range_step():
    from src.api.app import app

    client = TestClient(app)
    response = client.post("/api/step", json={"step": 99999})
    assert response.status_code == 400
