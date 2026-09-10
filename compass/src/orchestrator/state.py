"""
Shared state schema passed between all COMPASS pipeline nodes.

Keep this schema additive: nodes should only ever add/update keys relevant
to their stage, never assume upstream keys have been cleared.
"""

from typing import TypedDict, List, Dict, Optional, Literal


class LogisticsSnapshot(TypedDict):
    """Normalized logistics network state at a point in time."""
    timestamp: str
    nodes: List[Dict]       # e.g. depots, ports, forward staging areas
    routes: List[Dict]      # edges between nodes with capacity/status
    inventory: Dict         # per-node inventory levels


class ThreatAssessment(TypedDict):
    """Output of the Threat Assessment agent."""
    contested_nodes: List[str]
    contested_routes: List[str]
    denial_probability: Dict[str, float]  # node/route id -> probability
    confidence: float


class Forecast(TypedDict):
    """Output of the Forecasting agent."""
    horizon_hours: int
    projected_throughput: Dict[str, float]
    projected_shortfalls: List[Dict]


class CourseOfAction(TypedDict):
    """A single candidate COA."""
    coa_id: str
    description: str
    affected_routes: List[str]
    estimated_cost: float
    estimated_risk: float
    rationale: str


class RiskEvaluation(TypedDict):
    """Scored COAs with tradeoff commentary."""
    coa_id: str
    risk_score: float
    tradeoff_summary: str


class CompassState(TypedDict, total=False):
    """Top-level graph state threaded through every node."""

    # Sensing
    raw_feeds: List[Dict]
    logistics_snapshot: LogisticsSnapshot
    # Per-route observed denial history (route_id -> bool), oldest to
    # newest, strictly *before* the current logistics_snapshot -- this is
    # what the rolling-baseline forecaster is scored/predicts against.
    # Populated by the sensing agent when real or synthetic historical
    # data is available; left empty/missing falls back to the simpler
    # threat_assessment-based forecast.
    denial_history: List[Dict[str, bool]]

    # Threat Assessment
    threat_assessment: ThreatAssessment

    # Forecasting
    forecast: Forecast

    # COA Generation
    candidate_coas: List[CourseOfAction]

    # Risk Evaluation
    risk_evaluations: List[RiskEvaluation]

    # Human Gate / Adjudication
    human_decision: Optional[Literal["approve", "reject", "request_alternatives"]]
    selected_coa_id: Optional[str]
    decision_rationale: Optional[str]

    # Control flow
    replan_requested: bool
    iteration: int
