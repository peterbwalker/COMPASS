"""
Risk / Tradeoff Evaluation Agent

Scores candidate COAs and uses Claude to produce a human-readable
tradeoff summary for each -- the explainability layer a human reviewer
sees at the human gate before adjudication.
"""

from src.orchestrator.state import CompassState, RiskEvaluation
from src.utils.llm_client import call_claude

_SYSTEM_PROMPT = """You are helping a military logistics decision-maker understand \
tradeoffs between courses of action in a contested logistics scenario. Given a \
single COA's details, write a concise 2-3 sentence plain-language tradeoff \
summary: what it costs, what risk it carries, and when it would make sense to \
choose it. Interpret the numbers, don't just restate them verbatim."""


def _build_prompt(coa: dict) -> str:
    return (
        f"COA: {coa['description']}\n"
        f"Affected routes: {coa['affected_routes']}\n"
        f"Estimated cost: {coa['estimated_cost']}\n"
        f"Estimated risk: {coa['estimated_risk']}\n"
        f"Rationale: {coa['rationale']}\n"
    )


def risk_evaluation_agent(state: CompassState) -> CompassState:
    coas = state["candidate_coas"]

    evaluations = []
    for coa in coas:
        prompt = _build_prompt(coa)
        try:
            summary = call_claude(prompt, system=_SYSTEM_PROMPT, max_tokens=200)
        except RuntimeError:
            # No API key configured -- degrade gracefully rather than
            # crashing the pipeline, but make the degradation obvious.
            summary = (
                f"[LLM unavailable — set ANTHROPIC_API_KEY] "
                f"Cost {coa['estimated_cost']}, risk {coa['estimated_risk']}."
            )
        evaluations.append(
            RiskEvaluation(
                coa_id=coa["coa_id"],
                risk_score=coa["estimated_risk"],
                tradeoff_summary=summary,
            )
        )
    return {"risk_evaluations": evaluations}
