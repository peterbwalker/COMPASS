"""
Rolling denial-rate baseline forecasting model.

The simplest reasonable forecasting baseline: for each route, take a
rolling average of its recently observed denial outcomes as an estimate
of its near-term denial probability, then project throughput and
shortfalls against that estimate.

This exists to establish a reference point. Any more sophisticated model
(time-series, GNN, etc.) that gets prototyped later should be judged on
whether it actually beats this baseline -- not just on whether it beats
"no model at all."
"""

from typing import Dict, List

from src.orchestrator.state import Forecast


def rolling_denial_rate(
    history: List[Dict[str, bool]],
    window: int = 4,
    shrinkage_k: float = 0.0,
    shrinkage_prior: float = 0.0,
) -> Dict[str, float]:
    """
    Compute each route's rolling denial rate over the last `window` steps
    of observed history.

    Args:
        history: per-timestep denial dicts (route_id -> bool), ordered
            oldest to newest, as produced by
            generate_scenario()["ground_truth_denials"].
        window: number of most recent timesteps to average over.
        shrinkage_k: pseudo-count of "prior" observations to blend in.
            0 (default) disables shrinkage and reproduces a plain rolling
            average. On short windows, a raw average swings to extreme
            predictions (0.0 or 1.0) on very little evidence, which is
            expensive under Brier scoring even when directionally
            correct more often than not. Shrinkage blends the estimate
            toward `shrinkage_prior`, weighted as if `shrinkage_k` extra
            observations at that prior value had been seen -- a standard
            way to tame small-sample estimates (cf. Laplace smoothing /
            Bayesian shrinkage). Tune this like any other hyperparameter;
            it's not free -- too much shrinkage just reproduces the flat
            base-rate guess.
        shrinkage_prior: the probability to shrink toward, typically the
            overall base denial rate across the scenario.

    Returns:
        route_id -> estimated denial probability (0.0-1.0)
    """
    if not history:
        return {}

    recent = history[-window:]
    route_ids = {rid for step in recent for rid in step}

    rates = {}
    for route_id in route_ids:
        observations = [step[route_id] for step in recent if route_id in step]
        n = len(observations)
        if n == 0:
            rates[route_id] = shrinkage_prior
            continue
        raw_sum = sum(observations)
        rates[route_id] = (raw_sum + shrinkage_k * shrinkage_prior) / (n + shrinkage_k)
    return rates


def rolling_baseline_forecast(
    history: List[Dict[str, bool]],
    routes: List[Dict],
    window: int = 4,
    horizon_hours: int = 24,
    shortfall_threshold: float = 0.5,
    shrinkage_k: float = 0.0,
    shrinkage_prior: float = 0.0,
) -> Forecast:
    """
    Project throughput and shortfalls using the rolling denial-rate
    baseline. Assumes the recent rolling rate persists over the forecast
    horizon -- naive, but a useful reference point. See
    `rolling_denial_rate` for what `shrinkage_k`/`shrinkage_prior` do.
    """
    denial_rates = rolling_denial_rate(
        history, window=window, shrinkage_k=shrinkage_k, shrinkage_prior=shrinkage_prior
    )

    projected_throughput = {}
    projected_shortfalls = []

    for route in routes:
        route_id = route["id"]
        rate = denial_rates.get(route_id, 0.0)
        capacity = route.get("capacity", 1.0)

        projected_throughput[route_id] = capacity * (1.0 - rate)

        if rate >= shortfall_threshold:
            projected_shortfalls.append({
                "route_id": route_id,
                "projected_denial_rate": rate,
                "risk": "high" if rate >= 0.75 else "moderate",
            })

    return Forecast(
        horizon_hours=horizon_hours,
        projected_throughput=projected_throughput,
        projected_shortfalls=projected_shortfalls,
    )


def backtest_rolling_baseline(
    ground_truth_denials: List[Dict[str, bool]],
    window: int = 4,
    shrinkage_k: float = 0.0,
    shrinkage_prior: float = 0.0,
) -> Dict:
    """
    Walk through a scenario timestep by timestep, predicting each route's
    denial rate from the preceding `window` steps and scoring against the
    actual next-step outcome using Brier score (mean squared error
    between predicted probability and the 0/1 outcome -- lower is better,
    0 is a perfect forecast, 0.25 is what you'd get from always guessing
    50%).

    Returns per-route mean Brier score plus an overall average, so a
    later model has a concrete number to beat. Pass `shrinkage_k` > 0
    with `shrinkage_prior` set to the scenario's overall base denial rate
    to evaluate the shrunk estimator instead of the raw rolling average.
    """
    route_ids = set()
    for step in ground_truth_denials:
        route_ids.update(step.keys())

    scores = {rid: [] for rid in route_ids}

    for t in range(window, len(ground_truth_denials) - 1):
        history_slice = ground_truth_denials[:t]
        predicted = rolling_denial_rate(
            history_slice, window=window, shrinkage_k=shrinkage_k, shrinkage_prior=shrinkage_prior
        )
        actual_next = ground_truth_denials[t]

        for rid in route_ids:
            if rid in actual_next:
                p = predicted.get(rid, shrinkage_prior)
                actual = float(actual_next[rid])
                scores[rid].append((p - actual) ** 2)

    per_route_brier = {
        rid: (sum(vals) / len(vals) if vals else None) for rid, vals in scores.items()
    }
    valid = [v for v in per_route_brier.values() if v is not None]
    overall = sum(valid) / len(valid) if valid else None

    return {"per_route": per_route_brier, "overall": overall}
