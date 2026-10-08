"""Casualty generation. Per-patient attributes use a per-patient RNG so that
the same (scenario, seed) yields identical patients under every policy
(common random numbers)."""
from __future__ import annotations

import random
from typing import List

from .models import Acuity, PatientSpec, Scenario, Service
from .params import ACUITY_MIX, FINAL_ROLE_MIX, P_DCS, P_ICU


def _choice(rng: random.Random, weights: dict):
    keys = list(weights)
    return rng.choices(keys, weights=[weights[k] for k in keys])[0]


def generate_casualties(sc: Scenario, seed: int) -> List[PatientSpec]:
    arr_rng = random.Random(f"arrivals|{seed}")
    zone = {z.id: z for z in sc.zones}
    raw = []
    for s in sc.streams:
        if s.rate_per_h <= 0:
            continue
        t = s.start_h
        while True:
            t += arr_rng.expovariate(s.rate_per_h)
            if t >= s.end_h:
                break
            raw.append((t, s))
    raw.sort(key=lambda x: x[0])

    out: List[PatientSpec] = []
    for i, (t, s) in enumerate(raw):
        r = random.Random(f"patient|{seed}|{i}")
        svc = Service(_choice(r, s.service_mix))
        acu = Acuity(_choice(r, ACUITY_MIX))
        final = int(_choice(r, FINAL_ROLE_MIX[acu.value]))
        dcs = final >= 2 and r.random() < P_DCS[acu.value]
        icu = final >= 3 and r.random() < P_ICU[acu.value]
        E = r.expovariate(1.0)
        tac = min(3.0, 0.15 + r.expovariate(1.0 / max(0.05, zone[s.zone_id].tacevac_mean_h)))
        out.append(PatientSpec(f"P{i+1:04d}", svc, s.zone_id, round(t, 4), acu, final, dcs, icu,
                               E, round(tac, 4), r.random()))
    return out
