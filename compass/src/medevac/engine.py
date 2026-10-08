"""Discrete-event MEDEVAC engine: point of injury -> Role 1 -> 2 -> 3 -> 4.

Mortality is hazard-based. Each patient carries an Exp(1) threshold E (common
random number across policies) and dies when the cumulative hazard integrated
over their care trajectory reaches E. Hazard is piecewise-constant in
(acuity, highest care level, state), so death events are scheduled exactly.

Policies only *propose* assignments; the engine validates every one (capacity,
range, closures, asset availability), so a buggy policy cannot cheat physics.
"""
from __future__ import annotations

import heapq
import itertools
import random
from dataclasses import dataclass
from typing import Dict, List, Optional

from .geo import haversine_km, path_intersects
from .models import ACUITY_RANK, AssetSpec, Facility, PatientSpec, Scenario, Service
from .params import DEFAULT_PARAMS, HAZARD_PER_H

(EV_CAS, EV_R1, EV_PICKUP, EV_ARRIVE, EV_SURG_DONE, EV_READY, EV_DEATH, EV_DISCHARGE,
 EV_TICK, EV_ASSET_FREE, EV_LOSS_OUT, EV_LOSS_LOADED, EV_LOSS_RET) = range(13)

TERMINAL = ("DONE", "DIED")


class PS:
    """Runtime patient state."""

    def __init__(self, spec: PatientSpec):
        self.spec = spec
        self.id = spec.id
        self.service = spec.service
        self.acuity = spec.acuity
        self.final_role = spec.final_role
        self.needs_dcs = spec.needs_dcs
        self.needs_icu = spec.needs_icu
        self.state = "PRE"            # PRE, TACEVAC, AWAITING, HOLD, QUEUED_SURGERY, IN_SURGERY, IN_TRANSIT, DONE, DIED
        self.loc: Optional[str] = None
        self.care = 0
        self.surgery_done = False
        self.cum = 0.0
        self.rate = 0.0
        self.last_t = spec.t0
        self.ver = 0
        self.ready_t = 0.0
        self.assigned: Optional[int] = None
        self.transit_mult = 1.0
        self.t_queue = 0.0
        self.surg_end = 0.0
        # milestones
        self.t_r1 = self.t_surg_start = self.t_surg_end = None
        self.t_r2 = self.t_r3 = self.t_r4 = self.t_done = self.t_death = None
        self.cause: Optional[str] = None
        self.legs = 0
        self.cross_legs = 0
        self.log: List[tuple] = []


class AS:
    def __init__(self, spec: AssetSpec):
        self.spec = spec
        self.id = spec.id
        self.alive = True
        self.busy = False
        self.free_at = 0.0
        self.missions = 0
        self.busy_h = 0.0


class FS:
    def __init__(self, spec: Facility):
        self.spec = spec
        self.occ: set = set()
        self.inbound = 0
        self.queue: List[PS] = []
        self.on_table: List[PS] = []
        self.peak_occ = 0
        self.peak_queue = 0


@dataclass
class Plan:
    t_pickup: float
    t_deliver: float
    t_return: float
    t_free: float
    risk_out: float
    risk_load: float
    risk_ret: float

    @property
    def risk_total(self) -> float:
        return 1 - (1 - self.risk_out) * (1 - self.risk_load) * (1 - self.risk_ret)


@dataclass
class Assignment:
    asset_id: str
    origin: str
    dest: str
    patient_ids: List[str]


@dataclass
class Mission:
    id: int
    asset_id: str
    origin: str
    dest: str
    patient_ids: List[str]
    t_depart: float
    plan: Plan
    outcome: str = "OK"
    boarded: Optional[List[str]] = None
    inbound_held: int = 0


class Sim:
    def __init__(self, sc: Scenario, patients: List[PatientSpec], policy, seed: int = 0,
                 keep_log: bool = True):
        self.sc = sc
        self.policy = policy
        self.seed = seed
        self.keep_log = keep_log
        self.params = {**DEFAULT_PARAMS, **sc.params}
        self.fac: Dict[str, Facility] = {f.id: f for f in sc.facilities}
        self.bases = {b.id: b for b in sc.bases}
        self.zone = {z.id: z for z in sc.zones}
        self.P: Dict[str, PS] = {s.id: PS(s) for s in patients}
        self.A: Dict[str, AS] = {a.id: AS(a) for a in sc.assets}
        self.F: Dict[str, FS] = {f.id: FS(f) for f in sc.facilities}
        self.t = 0.0
        self.end_time = sc.horizon_h + self.params["drain_h"]
        self.q: list = []
        self._seq = itertools.count()
        self.missions: Dict[int, Mission] = {}
        self._mid = itertools.count(1)
        self.mission_log: List[dict] = []
        self.unresolved = len(self.P)
        self.cas_pending = len(self.P)
        self.rejected = 0
        self.blocked_ticks = 0
        for p in self.P.values():
            self._push(p.spec.t0, EV_CAS, p.id)
        self._push(0.0, EV_TICK, None)

    # ------------------------------------------------------------------ utils
    def _push(self, t, kind, payload, extra=None):
        heapq.heappush(self.q, (t, next(self._seq), kind, payload, extra))

    def _u(self, key) -> float:
        return random.Random(f"{self.seed}|{key}").random()

    def node_ll(self, node_id: str):
        if node_id in self.fac:
            f = self.fac[node_id]
            return (f.lat, f.lon)
        b = self.bases[node_id]
        return (b.lat, b.lon)

    def dist(self, a: str, b: str) -> float:
        return haversine_km(self.node_ll(a), self.node_ll(b))

    def closed(self, fid: str, t0: float, t1: Optional[float] = None) -> bool:
        t1 = t0 if t1 is None else t1
        for c in self.sc.closures:
            if c.facility_id == fid and c.start_h <= t1 and c.end_h >= t0:
                return True
        return False

    def free_beds(self, fid: str) -> int:
        fs = self.F[fid]
        return fs.spec.beds - len(fs.occ) - fs.inbound

    def _log(self, p: PS, t: float, what: str):
        if self.keep_log:
            p.log.append((round(t, 3), what))

    # ----------------------------------------------------------------- hazard
    def base_rate(self, p: PS, care: Optional[int] = None) -> float:
        return HAZARD_PER_H[p.acuity.value][p.care if care is None else care]

    def _rate_now(self, p: PS) -> float:
        r = self.base_rate(p)
        role = self.fac[p.loc].role if p.loc else 0
        if p.state == "IN_TRANSIT":
            return r * p.transit_mult
        if p.state == "IN_SURGERY":
            return r * self.params["on_table_factor"]
        if p.needs_dcs and not p.surgery_done and role >= 2:
            return r * self.params["resus_factor"]
        return r

    def _rehaz(self, p: PS, t: float):
        if p.state in TERMINAL:
            return
        p.cum += p.rate * (t - p.last_t)
        p.last_t = t
        p.rate = self._rate_now(p)
        p.ver += 1
        if p.rate > 0:
            dt = (p.spec.E - p.cum) / p.rate
            self._push(t + max(dt, 0.0), EV_DEATH, p.id, p.ver)

    def _freeze(self, p: PS, t: float):
        p.cum += p.rate * (t - p.last_t)
        p.last_t = t
        p.rate = 0.0
        p.ver += 1

    # ------------------------------------------------------------ policy API
    def ready_patients(self, t: float) -> List[PS]:
        out = [p for p in self.P.values()
               if p.state == "AWAITING" and p.assigned is None and p.ready_t <= t + 1e-9]
        out.sort(key=lambda p: (ACUITY_RANK[p.acuity], p.ready_t, p.id))
        return out

    def idle_assets(self, t: float, service: Optional[Service] = None, exclude=()) -> List[AS]:
        return [a for a in self.A.values()
                if a.alive and not a.busy and a.free_at <= t + 1e-9 and a.id not in exclude
                and (service is None or a.spec.service == service)]

    def queue_wait_estimate(self, fid: str, t: float) -> float:
        fs = self.F[fid]
        n = fs.spec.or_tables
        if n <= 0:
            return 0.0
        rem = sum(max(0.0, p.surg_end - t) for p in fs.on_table)
        return (rem + len(fs.queue) * fs.spec.surgery_mean_h) / n

    def leg_risk(self, mode, pa, pb, t0: float, t1: float) -> float:
        surv = 1.0
        span = max(1e-6, t1 - t0)
        for th in self.sc.threats:
            if th.end_h <= t0 or th.start_h >= t1:
                continue
            lp = th.loss_prob.get(mode.value, 0.0)
            if lp <= 0:
                continue
            if not path_intersects(pa, pb, (th.lat, th.lon), th.radius_km):
                continue
            ov = (min(t1, th.end_h) - max(t0, th.start_h)) / span
            surv *= 1 - lp * min(1.0, ov)
        return 1 - surv

    def plan(self, asset_id: str, origin: str, dest: str, t: float) -> Optional[Plan]:
        spec = self.A[asset_id].spec
        d1 = self.dist(spec.base_id, origin)
        d2 = self.dist(origin, dest)
        d3 = self.dist(dest, spec.base_id)
        if d1 + d2 > spec.range_km or d3 > spec.range_km:
            return None
        v = spec.speed_kmh
        t_pick = t + d1 / v + spec.turn_h * 0.5
        t_del = t_pick + d2 / v + spec.turn_h * 0.5
        t_ret = t_del + d3 / v
        t_free = t_ret + spec.turn_h
        if self.closed(origin, t_pick - 0.5, t_pick + 0.5) or self.closed(dest, t_del - 1.0, t_del + 1.0):
            return None
        b, o, d = self.node_ll(spec.base_id), self.node_ll(origin), self.node_ll(dest)
        return Plan(t_pick, t_del, t_ret, t_free,
                    self.leg_risk(spec.mode, b, o, t, t_pick),
                    self.leg_risk(spec.mode, o, d, t_pick, t_del),
                    self.leg_risk(spec.mode, d, b, t_del, t_ret))

    # ------------------------------------------------------------- execution
    def _launch(self, asg: Assignment, t: float) -> bool:
        a = self.A.get(asg.asset_id)
        if a is None or not a.alive or a.busy or a.free_at > t + 1e-9:
            return False
        if asg.origin not in self.fac or asg.dest not in self.fac:
            return False
        o, d = self.fac[asg.origin], self.fac[asg.dest]
        legal = (o.role == 1 and d.role in (2, 3)) or (o.role == 2 and d.role == 3) or (o.role == 3 and d.role == 4)
        if not legal:
            return False
        pts = []
        for pid in asg.patient_ids:
            p = self.P.get(pid)
            if (p is None or p.state != "AWAITING" or p.assigned is not None or p.loc != asg.origin
                    or p.ready_t > t + 1e-9 or d.role > p.final_role):
                return False
            pts.append(p)
        if not pts or len(pts) > a.spec.litters or self.free_beds(asg.dest) < len(pts):
            return False
        pl = self.plan(asg.asset_id, asg.origin, asg.dest, t)
        if pl is None:
            return False

        mid = next(self._mid)
        m = Mission(mid, a.id, asg.origin, asg.dest, [p.id for p in pts], t, pl)
        self.missions[mid] = m
        a.busy = True
        a.missions += 1
        a.free_at = pl.t_free
        a.busy_h += min(pl.t_free, self.end_time) - t
        self.F[asg.dest].inbound += len(pts)
        m.inbound_held = len(pts)

        # critical-care slots: first crit_slots ICU-need patients ride with care, rest are penalised
        slots = a.spec.crit_slots
        for p in sorted(pts, key=lambda x: ACUITY_RANK[x.acuity]):
            p.assigned = mid
            if p.needs_icu:
                if slots > 0:
                    slots -= 1
                    p.transit_mult = 1.0
                else:
                    p.transit_mult = self.params["crit_no_ccatt_mult"]
            else:
                p.transit_mult = 1.0

        u = self._u(("loss", a.id, a.missions))
        if u < pl.risk_out:
            m.outcome = "LOST_OUTBOUND"
            self._push(t + (pl.t_pickup - t) * 0.5, EV_LOSS_OUT, mid)
        else:
            self._push(pl.t_pickup, EV_PICKUP, mid)
            if u < pl.risk_out + pl.risk_load:
                m.outcome = "LOST_LOADED"
                self._push(pl.t_pickup + (pl.t_deliver - pl.t_pickup) * 0.5, EV_LOSS_LOADED, mid)
            else:
                self._push(pl.t_deliver, EV_ARRIVE, mid)
                if u < pl.risk_out + pl.risk_load + pl.risk_ret:
                    m.outcome = "LOST_RETURN"
                    self._push(pl.t_deliver + (pl.t_return - pl.t_deliver) * 0.5, EV_LOSS_RET, mid)
                else:
                    self._push(pl.t_free, EV_ASSET_FREE, a.id)
        return True

    def _release_inbound(self, m: Mission, n: int):
        n = min(n, m.inbound_held)
        m.inbound_held -= n
        self.F[m.dest].inbound -= n

    def _arrive(self, p: PS, fid: str, t: float):
        fs = self.F[fid]
        f = fs.spec
        fs.occ.add(p.id)
        fs.peak_occ = max(fs.peak_occ, len(fs.occ))
        p.loc = fid
        p.assigned = None
        p.transit_mult = 1.0
        role = f.role
        if role == 1 and p.t_r1 is None:
            p.t_r1 = t
        if role == 2 and p.t_r2 is None:
            p.t_r2 = t
        if role == 3 and p.t_r3 is None:
            p.t_r3 = t
        if role == 4 and p.t_r4 is None:
            p.t_r4 = t
        self._log(p, t, f"arrive {fid}")
        if p.needs_dcs and not p.surgery_done:
            p.care = max(p.care, 1)
            if f.or_tables > 0:
                p.state = "QUEUED_SURGERY"
                p.t_queue = t
                fs.queue.append(p)
                fs.peak_queue = max(fs.peak_queue, len(fs.queue))
                self._rehaz(p, t)
                self._start_surgeries(fid, t)
                return
            p.state = "AWAITING"
            p.ready_t = t
            self._rehaz(p, t)
            return
        p.care = max(p.care, role)
        self._after_treatment(p, f, t, surgical=False)

    def _after_treatment(self, p: PS, f: Facility, t: float, surgical: bool):
        role = f.role
        if p.final_role <= role:
            p.state = "DONE"
            p.t_done = t
            self._freeze(p, t)
            self.unresolved -= 1
            self._log(p, t, f"done @ {f.id}")
            stay = {1: 0.0, 2: self.params["stay_r2_h"], 3: self.params["stay_r3_h"]}.get(role)
            if stay is None:
                return
            if stay <= 0:
                self.F[f.id].occ.discard(p.id)
            else:
                self._push(t + stay, EV_DISCHARGE, p.id)
            return
        if role == 1:
            hold = self.params["nonsurg_hold_r1_h"]
        elif surgical:
            hold = f.postop_hold_h
        else:
            hold = self.params[f"nonsurg_hold_r{role}_h"]
        p.state = "HOLD"
        p.ready_t = t + hold
        self._rehaz(p, t)
        self._push(p.ready_t, EV_READY, p.id)

    def _start_surgeries(self, fid: str, t: float):
        fs = self.F[fid]
        f = fs.spec
        while fs.queue and len(fs.on_table) < f.or_tables:
            fs.queue.sort(key=lambda p: (-p.rate, p.t_queue))
            p = fs.queue.pop(0)
            p.state = "IN_SURGERY"
            p.t_surg_start = t
            dur = f.surgery_mean_h * (0.6 + 0.8 * p.spec.surg_u)
            p.surg_end = t + dur
            fs.on_table.append(p)
            self._rehaz(p, t)
            self._push(t + dur, EV_SURG_DONE, p.id, p.ver)
            self._log(p, t, f"surgery start {fid}")

    def _kill(self, p: PS, t: float, cause: str):
        if p.state in TERMINAL:
            return
        prev_state, loc = p.state, p.loc
        p.cum += p.rate * (t - p.last_t)
        p.last_t = t
        p.rate = 0.0
        p.ver += 1
        if prev_state == "IN_SURGERY" and loc:
            fs = self.F[loc]
            if p in fs.on_table:
                fs.on_table.remove(p)
        if prev_state == "QUEUED_SURGERY" and loc:
            fs = self.F[loc]
            if p in fs.queue:
                fs.queue.remove(p)
        if loc:
            self.F[loc].occ.discard(p.id)
        if p.assigned is not None and prev_state != "IN_TRANSIT":
            m = self.missions.get(p.assigned)
            if m is not None:
                self._release_inbound(m, 1)
        p.state = "DIED"
        p.t_death = t
        p.cause = cause if cause else prev_state
        p.assigned = None
        self.unresolved -= 1
        self._log(p, t, f"DIED ({p.cause})")
        if prev_state == "IN_SURGERY" and loc:
            self._start_surgeries(loc, t)

    def _cause_for(self, p: PS) -> str:
        return {"PRE": "PRE_TACEVAC", "TACEVAC": "PRE_TACEVAC", "AWAITING": "AWAITING_LIFT",
                "HOLD": "POST_CARE_HOLD", "QUEUED_SURGERY": "SURGERY_QUEUE",
                "IN_SURGERY": "ON_TABLE", "IN_TRANSIT": "IN_TRANSIT"}.get(p.state, p.state)

    # ------------------------------------------------------------- main loop
    def run(self):
        while self.q:
            t, _, kind, payload, extra = heapq.heappop(self.q)
            if t > self.end_time + 1e-9:
                break
            self.t = t
            if kind == EV_CAS:
                self.cas_pending -= 1
                p = self.P[payload]
                p.state = "TACEVAC"
                p.last_t = t
                self._rehaz(p, t)
                self._push(t + p.spec.tacevac_h, EV_R1, p.id)
            elif kind == EV_R1:
                p = self.P[payload]
                if p.state == "TACEVAC":
                    self._arrive(p, self.zone[p.spec.zone_id].r1_id, t)
            elif kind == EV_DEATH:
                p = self.P[payload]
                if p.ver == extra and p.state not in TERMINAL:
                    self._kill(p, t, self._cause_for(p))
            elif kind == EV_READY:
                p = self.P[payload]
                if p.state == "HOLD":
                    p.state = "AWAITING"
                    self._log(p, t, "ready for evac")
            elif kind == EV_SURG_DONE:
                p = self.P[payload]
                if p.state == "IN_SURGERY" and p.ver == extra:
                    fs = self.F[p.loc]
                    fs.on_table.remove(p)
                    p.surgery_done = True
                    p.t_surg_end = t
                    p.care = max(p.care, fs.spec.role)
                    self._log(p, t, "surgery done")
                    self._after_treatment(p, fs.spec, t, surgical=True)
                    self._start_surgeries(fs.spec.id, t)
            elif kind == EV_DISCHARGE:
                p = self.P[payload]
                if p.loc:
                    self.F[p.loc].occ.discard(p.id)
            elif kind == EV_PICKUP:
                m = self.missions[payload]
                m.boarded = []
                a = self.A[m.asset_id]
                for pid in m.patient_ids:
                    p = self.P[pid]
                    if p.state != "AWAITING" or p.assigned != m.id:
                        continue
                    self.F[p.loc].occ.discard(pid)
                    p.state = "IN_TRANSIT"
                    p.legs += 1
                    if a.spec.service != p.service and a.spec.service != Service.JOINT:
                        p.cross_legs += 1
                    self._rehaz(p, t)
                    m.boarded.append(pid)
                    self._log(p, t, f"boarded {a.id} -> {m.dest}")
            elif kind == EV_ARRIVE:
                m = self.missions[payload]
                for pid in (m.boarded or []):
                    p = self.P[pid]
                    if p.state == "IN_TRANSIT":
                        self._arrive(p, m.dest, t)
                self._release_inbound(m, m.inbound_held)
                self._record(m)
            elif kind in (EV_LOSS_OUT, EV_LOSS_LOADED, EV_LOSS_RET):
                m = self.missions[payload]
                self.A[m.asset_id].alive = False
                self.A[m.asset_id].busy = False
                if kind == EV_LOSS_OUT:
                    for pid in m.patient_ids:
                        p = self.P[pid]
                        if p.assigned == m.id:
                            p.assigned = None
                            p.transit_mult = 1.0
                elif kind == EV_LOSS_LOADED:
                    for pid in (m.boarded or []):
                        p = self.P[pid]
                        if p.state == "IN_TRANSIT":
                            self._kill(p, t, "LOST_IN_TRANSIT")
                    for pid in m.patient_ids:
                        p = self.P[pid]
                        if p.state == "AWAITING" and p.assigned == m.id:
                            p.assigned = None
                if kind != EV_LOSS_RET:
                    self._release_inbound(m, m.inbound_held)
                    self._record(m)
            elif kind == EV_ASSET_FREE:
                a = self.A[payload]
                if a.alive:
                    a.busy = False
            elif kind == EV_TICK:
                self._tick(t)
                if self.unresolved > 0 and t + self.params["tick_h"] <= self.end_time:
                    self._push(t + self.params["tick_h"], EV_TICK, None)
            if self.unresolved == 0 and self.cas_pending == 0:
                break
        return self

    def _tick(self, t: float):
        before = len(self.ready_patients(t))
        if before == 0:
            return
        launched = 0
        for asg in self.policy.decide(self, t):
            if self._launch(asg, t):
                launched += 1
            else:
                self.rejected += 1
        if launched == 0:
            self.blocked_ticks += 1

    def _record(self, m: Mission):
        if not self.keep_log:
            return
        pl = m.plan
        self.mission_log.append({
            "id": m.id, "asset": m.asset_id, "origin": m.origin, "dest": m.dest,
            "patients": m.patient_ids, "boarded": m.boarded or [], "outcome": m.outcome,
            "t_depart": round(m.t_depart, 2), "t_pickup": round(pl.t_pickup, 2),
            "t_deliver": round(pl.t_deliver, 2), "t_return": round(pl.t_return, 2),
            "risk": round(pl.risk_total, 3),
        })
