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
from src.doctrine.retrieval import get_retriever

_SYSTEM_PROMPT = """You are a logistics planning assistant supporting a military \
decision-maker in a contested logistics environment. Given a forecast of \
projected shortfalls and throughput, propose 1-3 concrete courses of action \
(COAs) to mitigate risk. For each COA, provide a short description, the \
routes it affects, an estimated cost (arbitrary relative units), an \
estimated risk (0-1), and a one-sentence rationale grounded in the data \
you were given. If doctrine excerpts are provided below, ground your COAs \
in them where relevant and note which excerpt informed a COA in its \
rationale -- but do not fabricate a doctrinal citation if none of the \
provided excerpts actually apply to a given COA. Respond ONLY with a JSON \
array of objects with keys: description, affected_routes (list of route id \
strings), estimated_cost (number), estimated_risk (number 0-1), rationale. \
No prose outside the JSON."""

_CODE_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def _strip_code_fence(text: str) -> str:
    """
    Strip a leading/trailing markdown code fence (```json ... ``` or
    ``` ... ```) if present. Models frequently add this even when told
    to respond with JSON only -- handle it defensively rather than
    relying on prompt wording alone to prevent it.
    """
    return _CODE_FENCE_RE.sub("", text.strip()).strip()


def _doctrine_query(forecast: dict) -> str:
    """Build a retrieval query from the shortfall context -- keyword
    overlap with doctrine text (e.g. 'reroute', 'sustainment',
    'contested', route/node terminology) is what BM25 matches on."""
    route_ids = [s["route_id"] for s in forecast["projected_shortfalls"]]
    return "reroute contested logistics sustainment shortfall " + " ".join(route_ids)


def _format_doctrine_block(passages: list) -> str:
    if not passages:
        return ""
    lines = [f"[{p.source}] {p.text}" for p in passages]
    return "\nRelevant doctrine excerpts (cite the source filename if used):\n" + "\n---\n".join(lines) + "\n"


def _build_prompt(forecast: dict, doctrine_block: str) -> str:
    return (
        f"Forecast horizon: {forecast['horizon_hours']} hours\n"
        f"Projected shortfalls: {json.dumps(forecast['projected_shortfalls'])}\n"
        f"Projected throughput: {json.dumps(forecast['projected_throughput'])}\n"
        f"{doctrine_block}"
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

    retriever = get_retriever()
    passages = retriever.retrieve(_doctrine_query(forecast), k=3)
    doctrine_block = _format_doctrine_block(passages)

    prompt = _build_prompt(forecast, doctrine_block)
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

