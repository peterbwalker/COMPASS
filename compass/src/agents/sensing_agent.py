"""
Sensing / Ingestion Agent

Responsible for pulling in and normalizing multi-source logistics and
contested-environment data into a single LogisticsSnapshot.

Placeholder: replace `_ingest_raw_feeds` with real connectors
(transportation status APIs, GPS integrity feeds, comms status, etc.)
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
    snapshot = _ingest_raw_feeds(raw_feeds)
    return {"logistics_snapshot": snapshot}
