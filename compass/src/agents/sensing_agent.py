"""
Sensing / Ingestion Agent

Responsible for pulling in and normalizing multi-source logistics and
contested-environment data into a LogisticsSnapshot, plus surfacing any
available prior denial history for the forecasting agent.

Two input modes:
  1. Real/stub feed: raw_feeds is a plain list -> single hardcoded
     snapshot, no history. This is the original placeholder behavior;
     replace `_ingest_raw_feeds` with real connectors when available
     (transportation status APIs, GPS integrity feeds, comms status).
  2. Synthetic scenario replay: raw_feeds is a dict shaped like
     {"scenario": generate_scenario() output, "current_step": int}.
     Used to drive the pipeline against synthetic_data.py output for
     prototyping/demoing -- pulls snapshot[current_step] as "now" and
     ground_truth_denials[:current_step] as history (strictly prior,
     no leakage of the current/future steps into the forecast).
"""

from src.orchestrator.state import CompassState, LogisticsSnapshot


def _ingest_raw_feeds(raw_feeds: list) -> LogisticsSnapshot:
    """Stub normalization logic — replace with real parsing/fusion."""
    return LogisticsSnapshot(
        timestamp="1970-01-01T00:00:00Z",
        nodes=[{"id": "DEPOT_A", "status": "operational"}],
        routes=[{"id": "ROUTE_1", "from": "DEPOT_A", "to": "FSA_1", "status": "open"}],
        inventory={"DEPOT_A": {"fuel": 1000, "medical": 200}},
    )


def sensing_agent(state: CompassState) -> CompassState:
    raw_feeds = state.get("raw_feeds", [])

    if isinstance(raw_feeds, dict) and "scenario" in raw_feeds:
        scenario = raw_feeds["scenario"]
        step = raw_feeds.get("current_step", 0)

        snapshot = scenario["snapshots"][step]
        history = scenario["ground_truth_denials"][:step]  # strictly prior steps only

        return {"logistics_snapshot": snapshot, "denial_history": history}

    snapshot = _ingest_raw_feeds(raw_feeds)
    return {"logistics_snapshot": snapshot, "denial_history": []}
