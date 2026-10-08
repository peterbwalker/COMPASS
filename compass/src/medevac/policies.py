"""Evacuation dispatch policies.

stovepipe : organic lift only, strict Role chain, same-service destination first.
joint     : pooled lift across services, nearest/fastest destination, greedy.
optimized : pooled lift + cost-based assignment (expected hazard accrued, route
            loss risk, destination surgical-queue wait, asset opportunity cost,
            capability matching, bypass, bundling, adaptive strategic batching).

All three are priority-aware (acuity first). The baselines are not strawmen;
what differs is lift pooling, routing intelligence and queue/capacity awareness.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from .engine import AS, Assignment, PS, Sim
from .models import Acuity, Mode, Service

IMMEDIATE = (Acuity.IMM_SURG, Acuity.IMM_MED)


def legal_dest_ids(sim: Sim, p: PS, bypass: bool) -> List[str]:
    r = sim.fac[p.loc].role
    fr = p.final_role
    out = []
    for f in sim.sc.facilities:
        if f.id == p.loc:
            continue
        if r == 1:
            ok = f.role == 2 or (bypass and f.role == 3 and fr >= 3)
        elif r == 2:
            ok = f.role == 3 and fr >= 3
        elif r == 3:
            ok = f.role == 4 and fr >= 4
        else:
            ok = False
        if ok:
            out.append(f.id)
    return out


def _crit_penalised(a: AS, p: PS) -> bool:
    return p.needs_icu and a.spec.crit_slots == 0


class Policy:
    name = "base"

    def __init__(self, **params):
        self.params = {**self.defaults(), **params}

    @classmethod
    def defaults(cls) -> Dict[str, float]:
        return {}

    def decide(self, sim: Sim, t: float) -> List[Assignment]:  # pragma: no cover
        raise NotImplementedError

    # shared strategic-batch rule for Role 3 -> Role 4 moves
    def _strategic_ok(self, sim: Sim, group: List[PS], t: float) -> bool:
        pr = self.params
        if len(group) >= pr["batch_min"]:
            return True
        if any(p.acuity in IMMEDIATE and t - p.ready_t >= pr["imm_wait_h"] for p in group):
            return True
        return max(t - p.ready_t for p in group) >= pr["batch_max_wait_h"]


class GreedyPolicy(Policy):
    organic_only = False
    prefer_same_service_dest = False

    @classmethod
    def defaults(cls):
        return {"max_risk": 0.15, "batch_min": 6, "batch_max_wait_h": 12.0, "imm_wait_h": 99.0}

    def decide(self, sim: Sim, t: float) -> List[Assignment]:
        out: List[Assignment] = []
        claimed, used = set(), set()
        self._resv: Dict[str, int] = {}
        for p in sim.ready_patients(t):
            if p.id in claimed:
                continue
            origin = p.loc
            role = sim.fac[origin].role
            if role == 3:
                grp = [q for q in sim.ready_patients(t) if q.loc == origin and q.id not in claimed]
                if not self._strategic_ok(sim, grp, t):
                    continue
            best = self._best(sim, p, t, used)
            if best is None:
                continue
            a, d = best
            load = [p]
            for q in sim.ready_patients(t):
                if len(load) >= a.spec.litters or q.id in claimed or q is p or q.loc != origin:
                    continue
                if d not in legal_dest_ids(sim, q, False):
                    continue
                if self.organic_only and q.service != a.spec.service:
                    continue
                if self._free(sim, d) < len(load) + 1:
                    break
                load.append(q)
            for q in load:
                claimed.add(q.id)
            used.add(a.id)
            self._resv[d] = self._resv.get(d, 0) + len(load)
            out.append(Assignment(a.id, origin, d, [q.id for q in load]))
        return out

    def _free(self, sim: Sim, d: str) -> int:
        return sim.free_beds(d) - self._resv.get(d, 0)

    def _best(self, sim: Sim, p: PS, t: float, used):
        dests = [d for d in legal_dest_ids(sim, p, False)
                 if self._free(sim, d) >= 1 and not sim.closed(d, t)]
        if not dests:
            return None
        if self.organic_only:
            assets = sim.idle_assets(t, service=p.service, exclude=used)
        else:
            assets = sim.idle_assets(t, exclude=used)
        if not assets:
            return None
        origin = p.loc
        if self.prefer_same_service_dest:
            same = [d for d in dests if sim.fac[d].service == p.service]
            dests = sorted(same or dests, key=lambda d: sim.dist(origin, d))
            groups = [[d] for d in dests]
        else:
            groups = [dests]
        for g in groups:
            cands = []
            for d in g:
                for a in assets:
                    pl = sim.plan(a.id, origin, d, t)
                    if pl is None or pl.risk_total > self.params["max_risk"]:
                        continue
                    cands.append((_crit_penalised(a, p), pl.t_deliver, a, d))
            if cands:
                cands.sort(key=lambda c: (c[0], c[1]))
                return cands[0][2], cands[0][3]
        return None


class StovepipePolicy(GreedyPolicy):
    name = "stovepipe"
    organic_only = True
    prefer_same_service_dest = True


class JointPolicy(GreedyPolicy):
    name = "joint"


class OptimizedPolicy(Policy):
    name = "optimized"

    @classmethod
    def defaults(cls):
        return {
            "max_risk": 0.25,
            "loss_penalty": 1.0,        # expected-death equivalent of losing a loaded aircraft
            "asset_loss_cost": 0.05,    # cost of losing an (empty) asset
            "opp_cost_per_h": 0.004,    # opportunity cost per asset-hour (hazard-equivalent)
            "crit_reserve_penalty": 0.02,
            "fill_wait_h": 2.0,         # low-acuity patients wait up to this long to fill a lift
            "allow_bypass": 1.0,
            "batch_min": 4,
            "batch_max_wait_h": 6.0,
            "imm_wait_h": 1.0,
        }

    def decide(self, sim: Sim, t: float) -> List[Assignment]:
        pr = self.params
        out: List[Assignment] = []
        claimed, used = set(), set()
        resv: Dict[str, int] = {}
        ready = sorted(sim.ready_patients(t), key=lambda p: (-sim.base_rate(p), p.ready_t))
        for p in ready:
            if p.id in claimed:
                continue
            origin = p.loc
            if sim.fac[origin].role == 3:
                grp = [q for q in ready if q.loc == origin and q.id not in claimed]
                if not self._strategic_ok(sim, grp, t):
                    continue
            dests = [d for d in legal_dest_ids(sim, p, bool(pr["allow_bypass"]))
                     if sim.free_beds(d) - resv.get(d, 0) >= 1 and not sim.closed(d, t)]
            assets = sim.idle_assets(t, exclude=used)
            if not dests or not assets:
                continue
            same_origin = [q for q in ready if q.loc == origin and q.id not in claimed]
            options = []
            for d in dests:
                comp_n = sum(1 for q in same_origin if d in legal_dest_ids(sim, q, bool(pr["allow_bypass"])))
                for a in assets:
                    pl = sim.plan(a.id, origin, d, t)
                    if pl is None or pl.risk_total > pr["max_risk"]:
                        continue
                    options.append((self._cost(sim, p, a, d, pl, t, comp_n), a, d, pl))
            if not options:
                continue
            _, a, d, pl = min(options, key=lambda o: o[0])

            load = [p]
            # compatible companions: ICU-need first (so crit slots are used well), then by hazard
            comp = [q for q in same_origin if q is not p and
                    d in legal_dest_ids(sim, q, bool(pr["allow_bypass"]))]
            comp.sort(key=lambda q: (not q.needs_icu, -sim.base_rate(q)))
            slots = a.spec.crit_slots - (1 if p.needs_icu else 0)
            for q in comp:
                if len(load) >= a.spec.litters or sim.free_beds(d) - resv.get(d, 0) < len(load) + 1:
                    break
                if q.needs_icu:
                    if slots <= 0:
                        continue
                    slots -= 1
                load.append(q)

            # low-acuity fill-wait: do not burn a big lift on a lone low-acuity patient
            if (all(q.acuity not in IMMEDIATE for q in load) and sim.fac[origin].role < 3
                    and len(load) < min(3, a.spec.litters)
                    and t - min(q.ready_t for q in load) < pr["fill_wait_h"]):
                continue

            for q in load:
                claimed.add(q.id)
            used.add(a.id)
            resv[d] = resv.get(d, 0) + len(load)
            out.append(Assignment(a.id, origin, d, [q.id for q in load]))
        return out

    def _cost(self, sim: Sim, p: PS, a: AS, d: str, pl, t: float, comp_n: int) -> float:
        pr = self.params
        r = sim.base_rate(p)
        tmult = sim.params["crit_no_ccatt_mult"] if _crit_penalised(a, p) else 1.0
        wait = pl.t_pickup - t
        transit = pl.t_deliver - pl.t_pickup
        fd = sim.fac[d]
        pending_dcs = p.needs_dcs and not p.surgery_done and fd.or_tables > 0
        qwait = sim.queue_wait_estimate(d, pl.t_deliver) if pending_dcs else 0.0
        accrued = r * wait + r * tmult * transit + r * sim.params["resus_factor"] * qwait
        # route risk
        risk_cost = (pr["loss_penalty"] * pl.risk_load
                     + pl.risk_out * r * 4.0
                     + pr["asset_loss_cost"] * (pl.risk_out + pl.risk_ret))
        n_on = max(1, min(a.spec.litters, comp_n))
        opp = pr["opp_cost_per_h"] * (pl.t_free - t) / n_on
        # a stop short of the patient's target echelon commits future lift
        future = 0.0
        if fd.role < min(p.final_role, 3):
            future = pr["opp_cost_per_h"] * 2.0
        crit_res = 0.0
        if (a.spec.crit_slots >= 2 and not p.needs_icu
                and p.acuity in (Acuity.DELAYED, Acuity.MINIMAL)):
            crit_res = pr["crit_reserve_penalty"]
        return accrued + risk_cost + opp + future + crit_res


POLICIES = {"stovepipe": StovepipePolicy, "joint": JointPolicy, "optimized": OptimizedPolicy}


def make_policy(name: str, params: Optional[dict] = None) -> Policy:
    if name not in POLICIES:
        raise KeyError(f"unknown policy {name!r}; choose from {sorted(POLICIES)}")
    return POLICIES[name](**(params or {}))
