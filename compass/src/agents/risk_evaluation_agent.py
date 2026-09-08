"""
Risk / Tradeoff Evaluation Agent

Scores candidate COAs against commander's intent and risk tolerance, and
produces a human-readable tradeoff summary. This is a good place to model
decision-maker trust calibration and explainability requirements.
"""

from src.orchestrator.state import CompassState, RiskEvaluation


def risk_evaluation_agent(state: CompassState) -> CompassState:
    coas = state["candidate_coas"]

    evaluations = [
        RiskEvaluation(
            coa_id=coa["coa_id"],
            risk_score=coa["estimated_risk"],
            tradeoff_summary=(
                f"Cost {coa['estimated_cost']}, risk {coa['estimated_risk']} — "
                "stub summary, replace with real tradeoff modeling."
            ),
        )
        for coa in coas
    ]
    return {"risk_evaluations": evaluations}
