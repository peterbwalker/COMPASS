import math

import pytest

from src.medevac.casualties import generate_casualties
from src.medevac.engine import Sim
from src.medevac.evaluate import compare, run_once
from src.medevac.geo import gc_interpolate, haversine_km, path_intersects
from src.medevac.policies import POLICIES, legal_dest_ids, make_policy
from src.medevac.scenario import build_scenario

SC = build_scenario()


def test_haversine_known_distance():
    # Honolulu -> Guam is roughly 6,100 km
    d = haversine_km((21.36, -157.89), (13.45, 144.78))
    assert 6000 < d < 6300


def test_gc_interpolate_endpoints_and_midpoint():
    a, b = (20.0, 121.0), (26.0, 127.0)
    assert gc_interpolate(a, b, 0) == pytest.approx(a, abs=1e-6)
    assert gc_interpolate(a, b, 1) == pytest.approx(b, abs=1e-6)
    m = gc_interpolate(a, b, 0.5)
    assert haversine_km(a, m) == pytest.approx(haversine_km(m, b), rel=1e-3)


def test_path_intersects():
    assert path_intersects((18.0, 120.0), (23.0, 122.0), (20.8, 121.0), 100.0)
    assert not path_intersects((10.0, 118.0), (11.0, 119.0), (24.0, 125.0), 100.0)


def test_casualties_deterministic_and_valid():
    a, b = generate_casualties(SC, 7), generate_casualties(SC, 7)
    assert [p.id for p in a] == [p.id for p in b]
    assert [p.E for p in a] == [p.E for p in b]
    assert len(a) > 100
    for p in a:
        assert 1 <= p.final_role <= 4
        if p.needs_dcs:
            assert p.final_role >= 2
        assert p.E > 0


@pytest.mark.parametrize("pol", sorted(POLICIES))
def test_run_is_deterministic(pol):
    m1 = run_once(SC, pol, 3)["metrics"]
    m2 = run_once(SC, pol, 3)["metrics"]
    assert m1 == m2


@pytest.mark.parametrize("pol", sorted(POLICIES))
def test_conservation_and_invariants(pol):
    pats = generate_casualties(SC, 2)
    sim = Sim(SC, pats, make_policy(pol), seed=2).run()
    states = [p.state for p in sim.P.values()]
    done, died = states.count("DONE"), states.count("DIED")
    open_ = len(states) - done - died
    assert done + died + open_ == len(pats)
    assert sim.unresolved == open_
    for fs in sim.F.values():
        assert len(fs.occ) <= fs.spec.beds
    for p in sim.P.values():
        if p.state == "DONE":
            assert p.t_death is None and p.t_done is not None
        if p.state == "DIED":
            assert p.t_death is not None and p.t_death >= p.spec.t0
        # a patient never reaches a role beyond what they need
        if p.t_r4 is not None:
            assert p.final_role == 4
        if p.t_r3 is not None:
            assert p.final_role >= 3
    assert sim.rejected == 0


def test_stovepipe_never_uses_other_service_lift():
    m = run_once(SC, "stovepipe", 1)["metrics"]
    assert m["interservice_leg_share"] == 0.0


def test_no_threats_means_no_losses():
    sc = build_scenario(threats_on=False)
    m = run_once(sc, "joint", 1)["metrics"]
    assert m["missions_lost"] == 0


def test_no_lift_is_worse_than_lift():
    sc = build_scenario()
    base = run_once(sc, "joint", 1)["metrics"]["deaths"]
    sc2 = build_scenario()
    sc2.assets = []
    none = run_once(sc2, "joint", 1)["metrics"]["deaths"]
    assert none > base


def test_common_random_numbers_same_patients_across_policies():
    ids = {pol: [(p.id, p.E) for p in generate_casualties(SC, 5)] for pol in POLICIES}
    assert len({tuple(v) for v in ids.values()}) == 1


def test_legal_dests_respect_chain():
    pats = generate_casualties(SC, 1)
    sim = Sim(SC, pats, make_policy("joint"), seed=1)
    p = next(x for x in sim.P.values() if x.final_role >= 3)
    p.loc = "R1_BATANES"
    roles = {sim.fac[d].role for d in legal_dest_ids(sim, p, bypass=False)}
    assert roles == {2}
    roles_b = {sim.fac[d].role for d in legal_dest_ids(sim, p, bypass=True)}
    assert roles_b == {2, 3}
    p.loc = "R3_OKINAWA"
    p.final_role = 3
    assert legal_dest_ids(sim, p, bypass=False) == []


def test_compare_paired_structure():
    c = compare(SC, ["stovepipe", "joint"], [1, 2, 3])
    assert set(c["summary"]) == {"stovepipe", "joint"}
    assert "joint_minus_stovepipe" in c["paired_vs_first"]
    assert c["paired_vs_first"]["joint_minus_stovepipe"]["n"] == 3


def test_api_endpoints():
    from fastapi.testclient import TestClient
    from src.api.main import app
    c = TestClient(app)
    assert c.get("/api/medevac/health").json()["ok"]
    sc = c.get("/api/medevac/scenario").json()
    assert sc["notional"] is True and len(sc["facilities"]) >= 15
    assert set(c.get("/api/medevac/policies").json()) == set(POLICIES)
    r = c.post("/api/medevac/simulate", json={"policy": "joint", "seed": 1, "detail": False})
    assert r.status_code == 200 and "metrics" in r.json()
    r = c.post("/api/medevac/simulate", json={"policy": "nope"})
    assert r.status_code == 400
    r = c.post("/api/medevac/compare", json={"policies": ["joint", "optimized"], "n_seeds": 2})
    assert r.status_code == 200 and "paired_vs_first" in r.json()
