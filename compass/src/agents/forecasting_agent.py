"""
Predictive / Forecasting Agent

Projects future logistics network state. Uses the rolling denial-rate
baseline (src/utils/baselines.py) against observed history when
available -- this is the model validated in prototyping: a short window
(2 steps) with Bayesian shrinkage toward the historical base rate beats
both a naive rolling average and a flat base-rate guess on the
persistent synthetic threat data (see docs/architecture.md for the
backtest numbers). Falls back to the simpler threat-assessment-based
heuristic when no history is available (e.g. cold start, or a real feed
that hasn't accumulated observations yet).

These defaults (window=2, shrinkage_k=4) came from backtesting against
synthetic_data.py's specific persistence parameters -- re-tune them if
the underlying contested_duration_range or denial probabilities change,
or once this runs against real data with different dynamics.
"""

from src.orchestrator.state import CompassState, Forecast
from src.utils.baselines import rolling_baseline_forecast

_MIN_HISTORY_FOR_ROLLING_MODEL = 3
_WINDOW = 2
_SHRINKAGE_K = 4.0


def _historical_base_rate(history: list) -> float:
    """Overall observed denial rate across all routes and all history --
    used as the shrinkage prior so it adapts to whatever scenario/feed
    is actually running, rather than a hardcoded number."""
    all_obs = [v for step in history for v in step.values()]
    return sum(all_obs) / len(all_obs) if all_obs else 0.0


def _fallback_forecast(state: CompassState) -> Forecast:
    """Original threat-assessment-based heuristic, used when there's not
    enough history for the rolling model to say anything meaningful."""
    threat = state["threat_assessment"]
    snapshot = state["logistics_snapshot"]

    shortfalls = []
    for route_id, prob in threat["denial_probability"].items():
        if prob > 0.5:
            shortfalls.append({"route_id": route_id, "risk": "high"})

    return Forecast(
        horizon_hours=24,
        projected_throughput={r["id"]: 1.0 for r in snapshot["routes"]},
        projected_shortfalls=shortfalls,
    )


def forecasting_agent(state: CompassState) -> CompassState:
    history = state.get("denial_history", [])

    if len(history) < _MIN_HISTORY_FOR_ROLLING_MODEL:
        return {"forecast": _fallback_forecast(state)}

    snapshot = state["logistics_snapshot"]
    prior = _historical_base_rate(history)

    forecast = rolling_baseline_forecast(
        history=history,
        routes=snapshot["routes"],
        window=_WINDOW,
        shrinkage_k=_SHRINKAGE_K,
        shrinkage_prior=prior,
        horizon_hours=24,
    )
    return {"forecast": forecast}
