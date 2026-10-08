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


# ------------------------------------------------------------------ advisor
import json as _json

from src.medevac.advisor import (ChangeRequest, apply_changes, extract_json, fallback_narrative,
                                 interpret, narrate, run_change)


def test_extract_json_handles_fences_and_chatter():
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json('Sure! Here you go: {"a": {"b": 2}} Hope that helps') == {"a": {"b": 2}}


def test_apply_changes_validates_and_drops_bad_items():
    ch = ChangeRequest(
        c17_count=1, threat_scale=2.0,
        add_closures=[{"facility_id": "R3_OKINAWA", "start_h": 30, "end_h": 40},
                      {"facility_id": "NOPE", "start_h": 1, "end_h": 2},
                      {"facility_id": "R3_GUAM", "start_h": 50, "end_h": 10}],
        remove_assets=["C130_1", "GHOST"],
        remove_by_mode=[{"mode": "SURFACE", "count": 5}, {"mode": "WARP", "count": 1}],
        facility_overrides=[{"facility_id": "R2_LAOAG", "or_tables": 3}],
        policy_params={"optimized": {"max_risk": 0.1, "bogus": 1}, "nopolicy": {"x": 1}},
        unsupported=["weather"])
    sc, applied, warn, pp = apply_changes(ch)
    assert any("R3_OKINAWA closed" in a for a in applied)
    assert sum(1 for a in sc.assets if a.id.startswith("C17")) == 1
    assert "C130_1" not in {a.id for a in sc.assets}
    assert not any(a.mode.value == "SURFACE" for a in sc.assets)
    assert next(f for f in sc.facilities if f.id == "R2_LAOAG").or_tables == 3
    assert pp == {"optimized": {"max_risk": 0.1}}
    joined = " | ".join(warn)
    for frag in ("NOPE", "invalid window", "GHOST", "WARP", "bogus", "nopolicy", "weather"):
        assert frag in joined


def test_interpret_retries_after_bad_json():
    calls = []

    def fake(system, user):
        calls.append(user)
        return "not json at all" if len(calls) == 1 else '```json\n{"summary": "x", "c17_count": 1}\n```'

    ch, _ = interpret("lose two C-17s", SC, fake)
    assert ch.c17_count == 1 and len(calls) == 2


def test_interpret_gives_up_cleanly():
    with pytest.raises(ValueError):
        interpret("x", SC, lambda s, u: "nope")


def test_run_change_and_narration_fallback_and_llm():
    ch = ChangeRequest(c17_count=1, add_closures=[{"facility_id": "R3_OKINAWA", "start_h": 30, "end_h": 44}])
    out = run_change("lose C-17s, Okinawa closes", ch, None, [1, 2, 3])
    assert out["narrative_by_llm"] is False and "Best policy" in out["narrative"]
    assert set(out["results"]["policies"]) == {"joint", "optimized"}
    for r in out["results"]["policies"].values():
        assert r["changed"]["mortality"] >= 0 and "ci95" in r["delta_deaths"]
    seen = {}

    def fake(system, user):
        seen["user"] = user
        return "LLM says hello"

    text, used = narrate("p", out["applied"], out["warnings"], out["results"], fake)
    assert used and text == "LLM says hello"
    assert "FACTS" in seen["user"]
    text2, used2 = narrate("p", [], [], out["results"], lambda s, u: (_ for _ in ()).throw(RuntimeError("down")))
    assert not used2 and "notional" in text2


def test_advisor_endpoints(monkeypatch):
    from fastapi.testclient import TestClient
    import src.api.medevac_routes as mr
    from src.api.main import app
    c = TestClient(app)

    monkeypatch.setattr(mr, "get_llm", lambda: None)
    assert c.post("/api/medevac/advisor", json={"prompt": "lose a C-17"}).status_code == 503

    def fake(system, user):
        if "FACTS" in user:
            return "Narrated."
        return _json.dumps({"summary": "one fewer C-17", "c17_count": 2})

    monkeypatch.setattr(mr, "get_llm", lambda: fake)
    r = c.post("/api/medevac/advisor", json={"prompt": "lose a C-17", "n_seeds": 2})
    assert r.status_code == 200
    body = r.json()
    assert body["narrative"] == "Narrated." and body["narrative_by_llm"] is True
    assert body["interpretation"]["c17_count"] == 2

    r = c.post("/api/medevac/whatif", json={"change": {"surge_scale": 1.5}, "n_seeds": 2})
    assert r.status_code == 200 and "results" in r.json()
    assert "facilities" in c.get("/api/medevac/catalog").json()

    monkeypatch.setattr(mr, "get_llm", lambda: (lambda s, u: "garbage"))
    assert c.post("/api/medevac/advisor", json={"prompt": "whatever happens"}).status_code == 502
