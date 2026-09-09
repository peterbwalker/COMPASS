"""
Course of Action (COA) Generation Agent

Generates candidate reroute/resupply/prioritization options given the
current forecast. Claude proposes and narrates the options; nothing here
checks real-world feasibility yet -- a classical solver/optimization
check should sit between this and the risk evaluation step before any
of this touches a real decision (see docs/architecture.md).
"""

import json
import re

from src.orchestrator.state import CompassState, CourseOfAction
from src.utils.llm_client import call_claude

_SYSTEM_PROMPT = """You are a logistics planning assistant supporting a military \
decision-maker in a contested logistics environment. Given a forecast of \
projected shortfalls and throughput, propose 1-3 concrete courses of action \
(COAs) to mitigate risk. For each COA, provide a short description, the \
routes it affects, an estimated cost (arbitrary relative units), an \
estimated risk (0-1), and a one-sentence rationale grounded in the data \
you were given. Respond ONLY with a JSON array of objects with keys: \
description, affected_routes (list of route id strings), estimated_cost \
(number), estimated_risk (number 0-1), rationale. No prose outside the JSON."""

_CODE_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def _strip_code_fence(text: str) -> str:
    """
    Strip a leading/trailing markdown code fence (```json ... ``` or
    ``` ... ```) if present. Models frequently add this even when told
    to respond with JSON only -- handle it defensively rather than
    relying on prompt wording alone to prevent it.
    """
    return _CODE_FENCE_RE.sub("", text.strip()).strip()


def _build_prompt(forecast: dict) -> str:
    return (
        f"Forecast horizon: {forecast['horizon_hours']} hours\n"
        f"Projected shortfalls: {json.dumps(forecast['projected_shortfalls'])}\n"
        f"Projected throughput: {json.dumps(forecast['projected_throughput'])}\n"
    )


def coa_generation_agent(state: CompassState) -> CompassState:
    forecast = state["forecast"]

    if not forecast["projected_shortfalls"]:
        return {
            "candidate_coas": [
                CourseOfAction(
                    coa_id="COA_HOLD",
                    description="No shortfalls projected — maintain current plan.",
                    affected_routes=[],
                    estimated_cost=0.0,
                    estimated_risk=0.0,
                    rationale="No action required based on current forecast.",
                )
            ]
        }

    prompt = _build_prompt(forecast)
    raw = call_claude(prompt, system=_SYSTEM_PROMPT)

    try:
        parsed = json.loads(_strip_code_fence(raw))
    except json.JSONDecodeError:
        # Fall back to a safe, clearly-flagged default rather than crashing
        # the pipeline on a malformed LLM response.
        parsed = [{
            "description": "LLM response could not be parsed — manual review required.",
            "affected_routes": [],
            "estimated_cost": 0.0,
            "estimated_risk": 1.0,
            "rationale": raw[:200],
        }]

    coas = [
        CourseOfAction(
            coa_id=f"COA_{i + 1}",
            description=item.get("description", ""),
            affected_routes=item.get("affected_routes", []),
            estimated_cost=float(item.get("estimated_cost", 0.0)),
            estimated_risk=float(item.get("estimated_risk", 0.5)),
            rationale=item.get("rationale", ""),
        )
        for i, item in enumerate(parsed)
    ]
    return {"candidate_coas": coas}

