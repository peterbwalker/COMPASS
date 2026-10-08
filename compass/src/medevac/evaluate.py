"""Single runs and Monte Carlo comparison with common random numbers."""
from __future__ import annotations

import math
import statistics as st
from typing import Dict, List, Optional

from .casualties import generate_casualties
from .engine import Sim
from .models import Scenario
from .policies import make_policy


def _pct(xs, q):
    if not xs:
        return None
    xs = sorted(xs)
    k = min(len(xs) - 1, max(0, int(round(q * (len(xs) - 1)))))
    return round(xs[k], 2)


def metrics(sim: Sim) -> dict:
    P = list(sim.P.values())
    n = len(P)
    died = [p for p in P if p.state == "DIED"]
    done = [p for p in P if p.state == "DONE"]
    open_ = [p for p in P if p.state not in ("DONE", "DIED")]
    evac_req = [p for p in P if p.final_role >= 2]

    def rate(sub, pred):
        return round(sum(1 for p in sub if pred(p)) / len(sub), 4) if sub else None

    causes: Dict[str, int] = {}
    for p in died:
        causes[p.cause or "?"] = causes.get(p.cause or "?", 0) + 1

    dcs = [p for p in P if p.needs_dcs]
    tt_surg = [p.t_surg_start - p.spec.t0 for p in dcs if p.t_surg_start is not None]
    tt_r3 = [p.t_r3 - p.spec.t0 for p in P if p.t_r3 is not None]
    tt_r4 = [p.t_r4 - p.spec.t0 for p in P if p.t_r4 is not None]

    by_ac = {}
    for ac in ("IMM_SURG", "IMM_MED", "DELAYED", "MINIMAL"):
        sub = [p for p in P if p.acuity.value == ac]
        by_ac[ac] = {"n": len(sub), "mortality": rate(sub, lambda p: p.state == "DIED")}

    legs = sum(p.legs for p in P)
    cross = sum(p.cross_legs for p in P)
    util: Dict[str, dict] = {}
    for a in sim.A.values():
        u = util.setdefault(a.spec.mode.value, {"assets": 0, "lost": 0, "busy_h": 0.0, "missions": 0})
        u["assets"] += 1
        u["lost"] += 0 if a.alive else 1
        u["busy_h"] += a.busy_h
        u["missions"] += a.missions
    span = max(1.0, sim.t)
    for u in util.values():
        u["utilization"] = round(u["busy_h"] / (u["assets"] * span), 3)
        u["busy_h"] = round(u["busy_h"], 1)

    ms = list(sim.missions.values())
    loads = [len(m.boarded or []) for m in ms if m.boarded is not None]
    return {
        "n_casualties": n,
        "n_evac_required": len(evac_req),
        "deaths": len(died),
        "mortality": round(len(died) / n, 4) if n else 0.0,
        "mortality_by_acuity": by_ac,
        "death_causes": causes,
        "survivors_done": len(done),
        "unresolved_at_end": len(open_),
        "dcs_patients": len(dcs),
        "time_to_surgery_h": {"median": _pct(tt_surg, .5), "p90": _pct(tt_surg, .9)},
        "pct_dcs_within_2h": rate(dcs, lambda p: p.t_surg_start is not None and p.t_surg_start - p.spec.t0 <= 2),
        "pct_dcs_within_6h": rate(dcs, lambda p: p.t_surg_start is not None and p.t_surg_start - p.spec.t0 <= 6),
        "time_to_r3_h": {"median": _pct(tt_r3, .5), "p90": _pct(tt_r3, .9)},
        "time_to_r4_h": {"median": _pct(tt_r4, .5), "p90": _pct(tt_r4, .9)},
        "missions": len(ms),
        "missions_lost": sum(1 for m in ms if m.outcome != "OK"),
        "mean_load": round(sum(loads) / len(loads), 2) if loads else 0.0,
        "interservice_leg_share": round(cross / legs, 4) if legs else 0.0,
        "lift_utilization": util,
        "peak_surgery_queue": {f.spec.id: f.peak_queue for f in sim.F.values() if f.spec.or_tables and f.peak_queue},
        "rejected_assignments": sim.rejected,
        "sim_end_h": round(sim.t, 1),
    }


def run_once(sc: Scenario, policy_name: str, seed: int, policy_params: Optional[dict] = None,
             detail: bool = False) -> dict:
    patients = generate_casualties(sc, seed)
    sim = Sim(sc, patients, make_policy(policy_name, policy_params), seed=seed, keep_log=detail)
    sim.run()
    out = {"policy": policy_name, "seed": seed, "metrics": metrics(sim)}
    if detail:
        out["missions"] = sim.mission_log
        out["patients"] = [{
            "id": p.id, "service": p.service.value, "zone": p.spec.zone_id, "t0": p.spec.t0,
            "acuity": p.acuity.value, "final_role": p.final_role, "needs_dcs": p.needs_dcs,
            "needs_icu": p.needs_icu, "state": p.state, "cause": p.cause,
            "t_r1": p.t_r1, "t_surg_start": p.t_surg_start, "t_r2": p.t_r2, "t_r3": p.t_r3,
            "t_r4": p.t_r4, "t_done": p.t_done, "t_death": p.t_death, "log": p.log,
        } for p in sim.P.values()]
    return out


def _agg(xs: List[float]) -> dict:
    if not xs:
        return {"mean": None}
    m = sum(xs) / len(xs)
    sd = st.pstdev(xs) if len(xs) > 1 else 0.0
    se = sd / math.sqrt(len(xs)) if len(xs) > 1 else 0.0
    return {"mean": round(m, 4), "ci95": [round(m - 1.96 * se, 4), round(m + 1.96 * se, 4)]}


KEYS = ["mortality", "deaths", "unresolved_at_end", "pct_dcs_within_2h", "pct_dcs_within_6h",
        "missions_lost", "mean_load", "interservice_leg_share"]


def _job(args):
    sc, pol, seed, params = args
    return run_once(sc, pol, seed, params)["metrics"]


def compare(sc: Scenario, policies: List[str], seeds: List[int],
            policy_params: Optional[Dict[str, dict]] = None, workers: int = 1) -> dict:
    policy_params = policy_params or {}
    jobs = [(sc, pol, s, policy_params.get(pol)) for s in seeds for pol in policies]
    if workers > 1 and len(jobs) > 3:
        from concurrent.futures import ProcessPoolExecutor
        with ProcessPoolExecutor(max_workers=workers) as ex:
            results = list(ex.map(_job, jobs, chunksize=2))
    else:
        results = [_job(j) for j in jobs]
    runs: Dict[str, List[dict]] = {p: [] for p in policies}
    for (_, pol, _, _), m in zip(jobs, results):
        runs[pol].append(m)
    summary = {}
    for pol, rs in runs.items():
        row = {k: _agg([r[k] for r in rs if r[k] is not None]) for k in KEYS}
        row["median_time_to_surgery_h"] = _agg([r["time_to_surgery_h"]["median"] for r in rs
                                                if r["time_to_surgery_h"]["median"] is not None])
        row["median_time_to_r4_h"] = _agg([r["time_to_r4_h"]["median"] for r in rs
                                           if r["time_to_r4_h"]["median"] is not None])
        summary[pol] = row
    paired = {}
    if len(policies) > 1:
        base = policies[0]
        for pol in policies[1:]:
            diffs = [runs[pol][i]["mortality"] - runs[base][i]["mortality"] for i in range(len(seeds))]
            dd = [runs[pol][i]["deaths"] - runs[base][i]["deaths"] for i in range(len(seeds))]
            paired[f"{pol}_minus_{base}"] = {"mortality": _agg(diffs), "deaths": _agg(dd),
                                             "wins": sum(1 for x in dd if x < 0), "ties": sum(1 for x in dd if x == 0),
                                             "n": len(seeds)}
    return {"seeds": seeds, "policies": policies, "summary": summary, "paired_vs_first": paired,
            "caveat": "All parameters are notional placeholders; relative comparisons only."}
