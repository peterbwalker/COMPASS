# COMPASS-MEDEVAC (backend)

Interservice casualty-evacuation simulator, point of injury -> Role 1 -> 2 -> 3 -> 4,
notional INDOPACOM scenario. Self-contained: no Anthropic key, no logistics imports.

## Run
    pip install fastapi uvicorn pydantic pytest httpx
    python -m pytest -q tests                # 17 tests
    uvicorn src.api.main:app --port 8000     # from the directory that contains src/

`src.api.main` mounts MEDEVAC onto the existing logistics app if it imports, otherwise
runs MEDEVAC-only. Existing `src/api/app.py` is untouched.

## Endpoints
- GET  /api/medevac/health
- GET  /api/medevac/scenario        facilities, bases, assets, zones, threats, closures, streams
- GET  /api/medevac/policies        defaults for each policy
- POST /api/medevac/simulate        {policy, seed, policy_params?, scenario?{surge_scale,threats_on,closures_on,c17_count,hospital_ship}, detail}
- POST /api/medevac/compare         {policies, n_seeds, base_seed, ...}  paired, common-random-number comparison

## Policies
stovepipe (organic lift, same-service destination) | joint (pooled lift, fastest destination)
| optimized (pooled + cost-based: hazard accrued, route loss risk, surgical-queue wait,
asset opportunity cost, capability matching, bypass, bundling, adaptive strategic batching).

## Layout
src/medevac/{geo,models,params,scenario,casualties,engine,policies,evaluate}.py
src/api/{medevac_routes,main}.py    tests/test_medevac.py    ASSUMPTIONS.md
