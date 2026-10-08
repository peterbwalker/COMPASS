"""FastAPI router for the MEDEVAC simulator. Mounted by src/api/app.py.

Stateless and self-contained: it does not touch the logistics pipeline or the
LLM client, so it can be demoed without an API key.
"""
from __future__ import annotations

import os
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.medevac.evaluate import compare, run_once
from src.medevac.policies import POLICIES, make_policy
from src.medevac.scenario import build_scenario

router = APIRouter(prefix="/api/medevac", tags=["medevac"])

MAX_SEEDS = 40
_WORKERS = max(1, min(8, (os.cpu_count() or 2) - 1))


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


def _scenario(o: ScenarioOptions):
    return build_scenario(surge_scale=o.surge_scale, threats_on=o.threats_on, closures_on=o.closures_on,
                          c17_count=o.c17_count, hospital_ship=o.hospital_ship, horizon_h=o.horizon_h)


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
