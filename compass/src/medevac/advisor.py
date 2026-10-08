"""LLM advisor for the MEDEVAC simulator.

The LLM never touches the simulator directly and never produces numbers.
  1. interpret(): plain-language request -> structured ChangeRequest (JSON).
     Every field is validated against the real scenario (ids, ranges); anything
     invalid is dropped and reported in `warnings`.
  2. whatif(): the simulator runs baseline vs changed scenario, paired by seed.
  3. narrate(): the LLM explains the computed facts. A deterministic fallback
     is used if the LLM is unavailable, so the numbers always come back.

`llm` is any callable (system: str, user: str) -> str, injected so tests can
use a fake and the deployment can use the Anthropic API.
"""
from __future__ import annotations

import copy
import json
import re
from collections import Counter
from typing import Callable, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

from .evaluate import _agg, _job
from .models import FacilityClosure, Mode, Scenario
from .policies import POLICIES
from .scenario import build_scenario

LLM = Callable[[str, str], str]


# --------------------------------------------------------------- schema
class ClosureChange(BaseModel):
    facility_id: str
    start_h: float
    end_h: float
    reason: str = "advisor"


class ModeRemoval(BaseModel):
    mode: str
    count: int = 1
    service: Optional[str] = None


class FacilityOverride(BaseModel):
    facility_id: str
    beds: Optional[int] = None
    or_tables: Optional[int] = None


class ChangeRequest(BaseModel):
    summary: str = ""
    surge_scale: Optional[float] = None
    threats_on: Optional[bool] = None
    closures_on: Optional[bool] = None
    hospital_ship: Optional[bool] = None
    c17_count: Optional[int] = None
    threat_scale: Optional[float] = None
    add_closures: List[ClosureChange] = Field(default_factory=list)
    remove_assets: List[str] = Field(default_factory=list)
    remove_by_mode: List[ModeRemoval] = Field(default_factory=list)
    facility_overrides: List[FacilityOverride] = Field(default_factory=list)
    policy_params: Dict[str, Dict[str, float]] = Field(default_factory=dict)
    policies: List[str] = Field(default_factory=list)
    unsupported: List[str] = Field(default_factory=list)


# ------------------------------------------------------------ JSON utils
def extract_json(text: str) -> dict:
    """Robust to code fences and chatter around the JSON object."""
    t = text.strip()
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", t, re.S)
    if m:
        t = m.group(1)
    else:
        i, j = t.find("{"), t.rfind("}")
        if i != -1 and j > i:
            t = t[i:j + 1]
    return json.loads(t)


def catalog(sc: Scenario) -> dict:
    return {
        "facilities": [{"id": f.id, "name": f.name, "role": f.role, "service": f.service.value,
                        "beds": f.beds, "or_tables": f.or_tables} for f in sc.facilities if f.role > 1],
        "assets": [{"id": a.id, "mode": a.mode.value, "service": a.service.value, "base": a.base_id}
                   for a in sc.assets],
        "modes": [m.value for m in Mode],
        "zones": [{"id": z.id, "name": z.name} for z in sc.zones],
        "threats": [{"id": t.id, "name": t.name, "start_h": t.start_h, "end_h": t.end_h} for t in sc.threats],
        "horizon_h": sc.horizon_h,
        "policies": sorted(POLICIES),
        "policy_params": {k: sorted(v.defaults()) for k, v in POLICIES.items()},
    }


INTERPRET_SYSTEM = """You translate a planner's what-if request into a JSON change request for a notional \
MEDEVAC simulator. Reply with ONE JSON object and nothing else.

Allowed keys (all optional): summary (string), surge_scale (0.1-4, multiplies casualty rates; 1 = baseline), \
threats_on (bool), closures_on (bool), hospital_ship (bool), c17_count (0-5 strategic aeromedical aircraft; baseline 3), \
threat_scale (0-3, multiplies all aircraft/ship loss probabilities; 1 = baseline), \
add_closures [{facility_id, start_h, end_h, reason}], remove_assets [asset ids], \
remove_by_mode [{mode, count, service?}], facility_overrides [{facility_id, beds?, or_tables?}], \
policy_params {policy_name: {param: number}}, policies [policy names to compare], \
unsupported [short strings for any part of the request the simulator cannot represent].

Use ONLY ids from the catalog. Times are hours from the start of the scenario. If the request is vague about \
timing, choose a reasonable value and say so in summary. If part of the request cannot be represented, put it in \
`unsupported` instead of guessing. Do not invent numbers about outcomes."""


def interpret(prompt: str, sc: Scenario, llm: LLM) -> Tuple[ChangeRequest, List[str]]:
    user = f"CATALOG:\n{json.dumps(catalog(sc))}\n\nREQUEST:\n{prompt}"
    last_err = ""
    for attempt in range(2):
        raw = llm(INTERPRET_SYSTEM, user if attempt == 0 else
                  user + f"\n\nYour previous reply was not valid ({last_err}). Reply with one JSON object only.")
        try:
            return ChangeRequest(**extract_json(raw)), []
        except Exception as exc:  # noqa: BLE001
            last_err = f"{type(exc).__name__}: {str(exc)[:120]}"
    raise ValueError(f"advisor could not produce a valid change request ({last_err})")


# ----------------------------------------------------------- apply changes
def apply_changes(ch: ChangeRequest) -> Tuple[Scenario, List[str], List[str], Dict[str, dict]]:
    """Returns (scenario, applied, warnings, policy_params). Invalid items are dropped, never fatal."""
    applied: List[str] = []
    warn: List[str] = []
    kw = {}
    if ch.surge_scale is not None:
        kw["surge_scale"] = min(4.0, max(0.1, ch.surge_scale))
        applied.append(f"casualty surge x{kw['surge_scale']:g}")
    for k in ("threats_on", "closures_on", "hospital_ship"):
        v = getattr(ch, k)
        if v is not None:
            kw[k] = v
            applied.append(f"{k} = {v}")
    if ch.c17_count is not None:
        kw["c17_count"] = min(5, max(0, ch.c17_count))
        applied.append(f"strategic aeromedical aircraft = {kw['c17_count']}")
    sc = build_scenario(**kw)
    fac = {f.id: f for f in sc.facilities}

    if ch.threat_scale is not None:
        s = min(3.0, max(0.0, ch.threat_scale))
        for th in sc.threats:
            th.loss_prob = {m: min(0.95, p * s) for m, p in th.loss_prob.items()}
        applied.append(f"threat loss probabilities x{s:g}")

    horizon = sc.horizon_h + sc.params.get("drain_h", 72.0)
    for c in ch.add_closures:
        if c.facility_id not in fac or fac[c.facility_id].role == 1:
            warn.append(f"closure ignored: unknown or unsupported facility '{c.facility_id}'")
        elif not (0 <= c.start_h < c.end_h <= horizon):
            warn.append(f"closure ignored: invalid window {c.start_h}-{c.end_h} h for {c.facility_id}")
        else:
            sc.closures.append(FacilityClosure(c.facility_id, c.start_h, c.end_h, c.reason))
            applied.append(f"{c.facility_id} closed {c.start_h:g}-{c.end_h:g} h")

    ids = {a.id for a in sc.assets}
    drop = set()
    for aid in ch.remove_assets:
        if aid in ids:
            drop.add(aid)
        else:
            warn.append(f"asset ignored: unknown id '{aid}'")
    for r in ch.remove_by_mode:
        mode = r.mode.upper()
        if mode not in {m.value for m in Mode}:
            warn.append(f"asset removal ignored: unknown mode '{r.mode}'")
            continue
        pool = [a for a in sc.assets if a.mode.value == mode and a.id not in drop
                and (r.service is None or a.service.value == r.service.upper())]
        take = pool[:max(0, r.count)]
        drop.update(a.id for a in take)
        if len(take) < r.count:
            warn.append(f"only {len(take)} of {r.count} {mode} assets available to remove")
    if drop:
        sc.assets = [a for a in sc.assets if a.id not in drop]
        applied.append(f"removed {len(drop)} asset(s): {', '.join(sorted(drop))}")

    for o in ch.facility_overrides:
        f = fac.get(o.facility_id)
        if f is None:
            warn.append(f"capacity change ignored: unknown facility '{o.facility_id}'")
            continue
        if o.beds is not None:
            f.beds = min(2000, max(1, o.beds))
        if o.or_tables is not None:
            f.or_tables = min(20, max(0, o.or_tables))
        applied.append(f"{f.id}: beds={f.beds}, OR tables={f.or_tables}")

    pparams: Dict[str, dict] = {}
    for pol, params in ch.policy_params.items():
        if pol not in POLICIES:
            warn.append(f"policy parameters ignored: unknown policy '{pol}'")
            continue
        ok = set(POLICIES[pol].defaults())
        for k, v in params.items():
            if k in ok:
                pparams.setdefault(pol, {})[k] = float(v)
                applied.append(f"{pol}.{k} = {v:g}")
            else:
                warn.append(f"policy parameter ignored: {pol}.{k}")
    for u in ch.unsupported:
        warn.append(f"not representable in the simulator: {u}")
    return sc, applied, warn, pparams


# ------------------------------------------------------------------ run
def _run_many(sc, policies, seeds, params, workers):
    jobs = [(sc, p, s, (params or {}).get(p)) for s in seeds for p in policies]
    if workers > 1 and len(jobs) > 3:
        from concurrent.futures import ProcessPoolExecutor
        with ProcessPoolExecutor(max_workers=workers) as ex:
            res = list(ex.map(_job, jobs, chunksize=2))
    else:
        res = [_job(j) for j in jobs]
    out: Dict[str, List[dict]] = {p: [] for p in policies}
    for (_, p, _, _), m in zip(jobs, res):
        out[p].append(m)
    return out


def _summ(runs: List[dict]) -> dict:
    causes = Counter()
    for r in runs:
        causes.update(r["death_causes"])
    n = len(runs)

    def mean(f):
        xs = [f(r) for r in runs if f(r) is not None]
        return round(sum(xs) / len(xs), 3) if xs else None

    return {
        "mortality": mean(lambda r: r["mortality"]),
        "deaths": mean(lambda r: r["deaths"]),
        "casualties": mean(lambda r: r["n_casualties"]),
        "pct_dcs_within_6h": mean(lambda r: r["pct_dcs_within_6h"]),
        "median_time_to_surgery_h": mean(lambda r: r["time_to_surgery_h"]["median"]),
        "median_time_to_r4_h": mean(lambda r: r["time_to_r4_h"]["median"]),
        "missions_lost": mean(lambda r: r["missions_lost"]),
        "unresolved_at_end": mean(lambda r: r["unresolved_at_end"]),
        "death_causes": {k: round(v / n, 1) for k, v in causes.most_common()},
    }


def whatif(changed: Scenario, policies: List[str], seeds: List[int],
           policy_params: Optional[Dict[str, dict]] = None, workers: int = 1,
           baseline: Optional[Scenario] = None) -> dict:
    policies = [p for p in policies if p in POLICIES] or ["joint", "optimized"]
    base_runs = _run_many(baseline or build_scenario(), policies, seeds, None, workers)
    new_runs = _run_many(changed, policies, seeds, policy_params, workers)
    out = {"seeds": seeds, "policies": {}}
    for p in policies:
        dm = [n["deaths"] - b["deaths"] for b, n in zip(base_runs[p], new_runs[p])]
        dr = [n["mortality"] - b["mortality"] for b, n in zip(base_runs[p], new_runs[p])]
        out["policies"][p] = {"baseline": _summ(base_runs[p]), "changed": _summ(new_runs[p]),
                              "delta_deaths": _agg(dm), "delta_mortality": _agg(dr)}
    best = min(policies, key=lambda p: out["policies"][p]["changed"]["mortality"])
    out["best_policy_after_change"] = best
    return out


# -------------------------------------------------------------- narrate
NARRATE_SYSTEM = """You are a plain-spoken analyst briefing a medical planner on simulation results. \
Use ONLY the numbers in the FACTS JSON; never invent or recompute figures. Lead with the answer to the request. \
Say which policy performs best after the change and by how much, whether the change in deaths is distinguishable \
from noise (a 95% interval that excludes zero is; one that spans zero is not), and use death_causes, \
time-to-surgery, missions_lost and unresolved_at_end to explain the mechanism only where the data supports it. \
Mention anything in warnings. State once that parameters are notional placeholders, so results compare policies \
inside this model and are not forecasts. 150-220 words, short paragraphs, no bullet lists, no headings."""


def fallback_narrative(prompt: str, applied: List[str], warnings: List[str], res: dict) -> str:
    lines = [f"Request: {prompt.strip()}", "Changes applied: " + ("; ".join(applied) or "none") + "."]
    for p, r in res["policies"].items():
        d, ci = r["delta_deaths"]["mean"], r["delta_deaths"]["ci95"]
        lines.append(f"{p}: mortality {r['baseline']['mortality']:.3f} -> {r['changed']['mortality']:.3f}; "
                     f"change in deaths per run {d:+.1f} (95% CI {ci[0]:+.1f} to {ci[1]:+.1f}).")
    lines.append(f"Best policy after the change: {res['best_policy_after_change']}.")
    if warnings:
        lines.append("Notes: " + "; ".join(warnings) + ".")
    lines.append("All parameters are notional placeholders; this compares policies inside the model only.")
    return " ".join(lines)


def narrate(prompt: str, applied: List[str], warnings: List[str], res: dict, llm: Optional[LLM]) -> Tuple[str, bool]:
    if llm is None:
        return fallback_narrative(prompt, applied, warnings, res), False
    facts = {"request": prompt, "applied_changes": applied, "warnings": warnings, "results": res}
    try:
        text = llm(NARRATE_SYSTEM, "FACTS:\n" + json.dumps(facts))
        if text and text.strip():
            return text.strip(), True
    except Exception:  # noqa: BLE001
        pass
    return fallback_narrative(prompt, applied, warnings, res), False


def advise(prompt: str, llm: LLM, seeds: List[int], workers: int = 1,
           default_policies: Optional[List[str]] = None) -> dict:
    base_sc = build_scenario()
    ch, _ = interpret(prompt, base_sc, llm)
    return run_change(prompt, ch, llm, seeds, workers, default_policies)


def run_change(prompt: str, ch: ChangeRequest, llm: Optional[LLM], seeds: List[int], workers: int = 1,
               default_policies: Optional[List[str]] = None) -> dict:
    sc, applied, warnings, pparams = apply_changes(ch)
    policies = ch.policies or default_policies or ["joint", "optimized"]
    res = whatif(sc, policies, seeds, pparams, workers)
    text, used = narrate(prompt, applied, warnings, res, llm)
    return {"interpretation": ch.model_dump(), "applied": applied, "warnings": warnings,
            "results": res, "narrative": text, "narrative_by_llm": used,
            "caveat": "All parameters are notional placeholders; relative comparisons only."}
