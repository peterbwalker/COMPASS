"""FastAPI router for the MEDEVAC simulator. Mounted by src/api/main.py.

Self-contained: does not touch the logistics pipeline. Only the advisor
endpoints use an LLM (Anthropic API, ANTHROPIC_API_KEY); everything else runs
without a key.
"""
from __future__ import annotations

import os
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.medevac.advisor import ChangeRequest, advise, catalog, run_change
from src.medevac.evaluate import compare, run_once
from src.medevac.policies import POLICIES
from src.medevac.scenario import build_scenario

router = APIRouter(prefix="/api/medevac", tags=["medevac"])

MAX_SEEDS = 40
_WORKERS = max(1, min(8, (os.cpu_count() or 2) - 1))


# ------------------------------------------------------------------ LLM hook
def anthropic_llm(system: str, user: str) -> str:
    import anthropic

    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY
    model = os.environ.get("COMPASS_MEDEVAC_MODEL", "claude-sonnet-5-5")
    msg = client.messages.create(model=model, max_tokens=1500, system=system,
                                 messages=[{"role": "user", "content": user}])
    return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")


def get_llm():
    """Returns the LLM callable, or None if no key is configured. Tests override this."""
    return anthropic_llm if os.environ.get("ANTHROPIC_API_KEY") else None


# ------------------------------------------------------------------- models
class ScenarioOptions(BaseModel):
    surge_scale: float = Field(1.0, ge=0.1, le=4.0)
    threats_on: bool = True
    closures_on: bool = True
    c17_count: int = Field(3, ge=0, le=5)
    hospital_ship: bool = True
    horizon_h: float = Field(120.0, ge=24, le=240)


class SimulateRequest(BaseModel):
    policy: str = "optimized"
    seed: int = 1
    policy_params: Optional[Dict[str, float]] = None
    scenario: ScenarioOptions = ScenarioOptions()
    detail: bool = True


class CompareRequest(BaseModel):
    policies: List[str] = ["stovepipe", "joint", "optimized"]
    n_seeds: int = Field(10, ge=1, le=MAX_SEEDS)
    base_seed: int = 1
    policy_params: Optional[Dict[str, Dict[str, float]]] = None
    scenario: ScenarioOptions = ScenarioOptions()


class AdvisorRequest(BaseModel):
    prompt: str = Field(..., min_length=3, max_length=2000)
    n_seeds: int = Field(8, ge=2, le=MAX_SEEDS)
    base_seed: int = 1


class WhatIfRequest(BaseModel):
    prompt: str = "(structured what-if)"
    change: ChangeRequest
    n_seeds: int = Field(8, ge=2, le=MAX_SEEDS)
    base_seed: int = 1
    narrate_with_llm: bool = False


def _scenario(o: ScenarioOptions):
    return build_scenario(surge_scale=o.surge_scale, threats_on=o.threats_on, closures_on=o.closures_on,
                          c17_count=o.c17_count, hospital_ship=o.hospital_ship, horizon_h=o.horizon_h)


# ---------------------------------------------------------------- endpoints
@router.get("/scenario")
def get_scenario(surge_scale: float = 1.0, threats_on: bool = True, closures_on: bool = True,
                 c17_count: int = 3, hospital_ship: bool = True):
    sc = _scenario(ScenarioOptions(surge_scale=surge_scale, threats_on=threats_on, closures_on=closures_on,
                                   c17_count=c17_count, hospital_ship=hospital_ship))
    d = sc.to_dict()
    d["notional_warning"] = "All capabilities, counts, rates and threat values are notional placeholders."
    return d


@router.get("/policies")
def get_policies():
    return {name: {"params": cls.defaults(), "doc": (cls.__doc__ or "").strip()}
            for name, cls in POLICIES.items()}


@router.get("/catalog")
def get_catalog():
    """Ids the advisor (and a UI) can reference in structured changes."""
    return catalog(build_scenario())


@router.post("/simulate")
def simulate(req: SimulateRequest):
    if req.policy not in POLICIES:
        raise HTTPException(400, f"unknown policy {req.policy!r}; choose from {sorted(POLICIES)}")
    return run_once(_scenario(req.scenario), req.policy, req.seed, req.policy_params, detail=req.detail)


@router.post("/compare")
def compare_policies(req: CompareRequest):
    bad = [p for p in req.policies if p not in POLICIES]
    if bad or not req.policies:
        raise HTTPException(400, f"unknown policies {bad}; choose from {sorted(POLICIES)}")
    seeds = list(range(req.base_seed, req.base_seed + req.n_seeds))
    return compare(_scenario(req.scenario), req.policies, seeds, req.policy_params, workers=_WORKERS)


@router.post("/advisor")
def advisor(req: AdvisorRequest):
    llm = get_llm()
    if llm is None:
        raise HTTPException(503, "Advisor needs ANTHROPIC_API_KEY set on the server. "
                                 "Use POST /api/medevac/whatif with a structured change instead.")
    seeds = list(range(req.base_seed, req.base_seed + req.n_seeds))
    try:
        return advise(req.prompt, llm, seeds, workers=_WORKERS)
    except ValueError as exc:
        raise HTTPException(502, str(exc))
    except Exception as exc:  # LLM / network failure
        raise HTTPException(502, f"advisor LLM call failed: {type(exc).__name__}: {str(exc)[:200]}")


@router.post("/whatif")
def whatif_endpoint(req: WhatIfRequest):
    """Structured what-if with no LLM interpretation step (UI-editable path)."""
    seeds = list(range(req.base_seed, req.base_seed + req.n_seeds))
    llm = get_llm() if req.narrate_with_llm else None
    return run_change(req.prompt, req.change, llm, seeds, workers=_WORKERS)
