"""
COMPASS backend API.

A thin FastAPI wrapper around the LangGraph pipeline and the synthetic
scenario generator, so a frontend can:
  1. Fetch the static scenario topology (nodes with coordinates, routes)
     once, to draw the base map.
  2. Step through the scenario timestep by timestep, running the full
     pipeline (sensing -> ... -> adjudication) at each step and getting
     back the snapshot, forecast, candidate COAs, risk evaluations, and
     final decision -- everything the UI needs to render that moment.

Run locally with:
    uvicorn src.api.app:app --reload --port 8000

Requires ANTHROPIC_API_KEY to be set in the environment for the
COA-generation/risk-evaluation LLM calls to work (see .env.example).
"""

from typing import Dict, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.orchestrator.graph import build_graph
from src.utils.synthetic_data import ScenarioConfig, generate_scenario

app = FastAPI(title="COMPASS API")

# Wide open for local dev (Vite's default port). Tighten this before
# deploying anywhere beyond your own machine.

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Scenario + compiled graph are built once at startup and held in memory.
# Fine for a single-user local prototyping/demo tool; would need a real
# session/store for multi-user deployment.
_scenario = generate_scenario(ScenarioConfig(horizon_hours=240, timestep_hours=6, seed=1))
_graph_app = build_graph()

# Per-step result cache. The pipeline makes real (billed, non-trivial
# latency) LLM calls for COA generation and risk evaluation, and the
# scenario/graph are deterministic for a given step -- so re-running the
# whole pipeline every time the UI revisits a step already computed is
# pure waste. Keyed by step number; cleared only by process restart or
# an explicit force_refresh request.
_step_cache: Dict[int, dict] = {}


class StepRequest(BaseModel):
    step: int
    force_refresh: bool = False
    user_prompt: Optional[str] = None


@app.get("/api/scenario")
def get_scenario():
    """Static topology for drawing the base map: nodes (with lat/lon),
    routes (without per-timestep state), and how many timesteps exist."""

    return {
        "nodes": _scenario["nodes"],
        "routes": _scenario["routes"],
        "num_steps": len(_scenario["snapshots"]),
    }


@app.post("/api/step")
def run_step(req: StepRequest):
    """Run the full pipeline for a given timestep and return everything
    the UI needs to render that moment: current route states, the
    forecast, candidate COAs, risk evaluations, and the final decision.

    Cached after the first computation for a given step -- pass
    force_refresh=true to bypass. A request with user_prompt (guided
    analysis) is always run fresh and never written into the cache, so
    it can't poison the plain-step cache other users/scrubbing rely on.
    """
    if not (0 <= req.step < len(_scenario["snapshots"])):
        raise HTTPException(
            status_code=400,
            detail=f"step must be between 0 and {len(_scenario['snapshots']) - 1}",
        )

    if not req.user_prompt and not req.force_refresh and req.step in _step_cache:
        return {**_step_cache[req.step], "cached": True}

    config = {"configurable": {"thread_id": f"ui-step-{req.step}"}}
    initial_state = {
        "raw_feeds": {"scenario": _scenario, "current_step": req.step},
        "replan_requested": False,
        "iteration": 0,

        "user_prompt": req.user_prompt,
    }

    _graph_app.invoke(initial_state, config=config)  # runs to the human gate
    final = _graph_app.invoke(None, config=config)  # resumes past it

    result = {
        "step": req.step,
        "snapshot": final["logistics_snapshot"],
        "forecast": final["forecast"],
        "candidate_coas": final["candidate_coas"],
        "risk_evaluations": final["risk_evaluations"],
        "selected_coa_id": final.get("selected_coa_id"),
        "decision_rationale": final.get("decision_rationale"),
    }

    if not req.user_prompt:
        _step_cache[req.step] = result
    return {**result, "cached": False}
