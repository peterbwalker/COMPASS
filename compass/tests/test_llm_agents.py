"""
Tests for the LLM-backed agents. These mock src.utils.llm_client.call_claude
so the test suite never makes a real API call or requires ANTHROPIC_API_KEY.

Note: these modules are imported via importlib rather than a plain
`import src.agents.risk_evaluation_agent as risk_mod`. That's because
src/agents/__init__.py does `from .risk_evaluation_agent import
risk_evaluation_agent` -- since the function has the same name as its
module, that re-export overwrites the `agents.risk_evaluation_agent`
package attribute with the function object, so a plain import-as would
silently hand you the function instead of the module. importlib pulls
straight from sys.modules, sidestepping that collision. (Same issue
applies to coa_generation_agent.)
"""

import importlib
import json

coa_mod = importlib.import_module("src.agents.coa_generation_agent")
risk_mod = importlib.import_module("src.agents.risk_evaluation_agent")


def test_coa_generation_parses_valid_llm_json(monkeypatch):
    fake_response = json.dumps([
        {
            "description": "Reroute via ROUTE_2",
            "affected_routes": ["ROUTE_2"],
            "estimated_cost": 50.0,
            "estimated_risk": 0.3,
            "rationale": "ROUTE_2 has spare capacity and lower denial risk.",
        }
    ])
    monkeypatch.setattr(coa_mod, "call_claude", lambda *a, **k: fake_response)

    state = {
        "forecast": {
            "horizon_hours": 24,
            "projected_throughput": {"ROUTE_1": 0.0, "ROUTE_2": 100.0},
            "projected_shortfalls": [{"route_id": "ROUTE_1", "risk": "high"}],
        }
    }
    result = coa_mod.coa_generation_agent(state)

    assert len(result["candidate_coas"]) == 1
    coa = result["candidate_coas"][0]
    assert coa["coa_id"] == "COA_1"
    assert coa["affected_routes"] == ["ROUTE_2"]
    assert coa["estimated_risk"] == 0.3


def test_coa_generation_no_shortfalls_skips_llm_call(monkeypatch):
    def fail_if_called(*a, **k):
        raise AssertionError("call_claude should not be called with no shortfalls")

    monkeypatch.setattr(coa_mod, "call_claude", fail_if_called)

    state = {
        "forecast": {
            "horizon_hours": 24,
            "projected_throughput": {"ROUTE_1": 100.0},
            "projected_shortfalls": [],
        }
    }
    result = coa_mod.coa_generation_agent(state)
    assert result["candidate_coas"][0]["coa_id"] == "COA_HOLD"


def test_coa_generation_handles_markdown_code_fence(monkeypatch):
    """Reproduces a real failure: Claude wraps JSON in ```json ... ``` even
    when told to respond with JSON only. This must parse successfully,
    not fall into the malformed-response fallback."""
    fenced_response = (
        "```json\n"
        "[\n"
        '  {"description": "Reroute via ROUTE_2", "affected_routes": ["ROUTE_2"], '
        '"estimated_cost": 75.0, "estimated_risk": 0.25, '
        '"rationale": "ROUTE_2 has spare capacity."}\n'
        "]\n"
        "```"
    )
    monkeypatch.setattr(coa_mod, "call_claude", lambda *a, **k: fenced_response)

    state = {
        "forecast": {
            "horizon_hours": 24,
            "projected_throughput": {"ROUTE_1": 0.0, "ROUTE_2": 100.0},
            "projected_shortfalls": [{"route_id": "ROUTE_1", "risk": "high"}],
        }
    }
    result = coa_mod.coa_generation_agent(state)

    coa = result["candidate_coas"][0]
    assert coa["description"] == "Reroute via ROUTE_2"
    assert coa["estimated_risk"] == 0.25
    assert "could not be parsed" not in coa["description"]


def test_coa_generation_handles_malformed_json_gracefully(monkeypatch):
    monkeypatch.setattr(coa_mod, "call_claude", lambda *a, **k: "not valid json")

    state = {
        "forecast": {
            "horizon_hours": 24,
            "projected_throughput": {},
            "projected_shortfalls": [{"route_id": "ROUTE_1", "risk": "high"}],
        }
    }
    result = coa_mod.coa_generation_agent(state)
    assert len(result["candidate_coas"]) == 1
    assert result["candidate_coas"][0]["estimated_risk"] == 1.0  # flagged for review


def test_risk_evaluation_uses_llm_summary(monkeypatch):
    monkeypatch.setattr(
        risk_mod, "call_claude", lambda *a, **k: "This COA trades moderate cost for reduced risk."
    )

    state = {
        "candidate_coas": [
            {
                "coa_id": "COA_1",
                "description": "Reroute via ROUTE_2",
                "affected_routes": ["ROUTE_2"],
                "estimated_cost": 50.0,
                "estimated_risk": 0.3,
                "rationale": "spare capacity",
            }
        ]
    }
    result = risk_mod.risk_evaluation_agent(state)

    assert result["risk_evaluations"][0]["coa_id"] == "COA_1"
    assert "moderate cost" in result["risk_evaluations"][0]["tradeoff_summary"]


def test_risk_evaluation_degrades_gracefully_without_api_key(monkeypatch):
    def raise_no_key(*a, **k):
        raise RuntimeError("ANTHROPIC_API_KEY is not set.")

    monkeypatch.setattr(risk_mod, "call_claude", raise_no_key)

    state = {
        "candidate_coas": [
            {
                "coa_id": "COA_1",
                "description": "Reroute via ROUTE_2",
                "affected_routes": ["ROUTE_2"],
                "estimated_cost": 50.0,
                "estimated_risk": 0.3,
                "rationale": "spare capacity",
            }
        ]
    }
    result = risk_mod.risk_evaluation_agent(state)
    assert "LLM unavailable" in result["risk_evaluations"][0]["tradeoff_summary"]
