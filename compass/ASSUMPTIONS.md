# MEDEVAC simulator: assumptions and limits

**Every quantitative value is a notional placeholder. Nothing here is validated or doctrine-sourced.
Outputs support relative comparison of policies inside this model only. They are not forecasts
of real casualties, survival, or force requirements.**

## What is real
Geography (public coordinates) and the structure of the problem: Role 1-4 chain, service-owned
lift, range/closure/threat constraints, surgical bottlenecks, bed limits, strategic batching.

## What is notional (replace before relying on anything)
- Hazard rates by acuity and care level (params.py `HAZARD_PER_H`), resuscitation / on-table factors.
- Acuity mix, final-echelon mix, surgery and ICU probabilities (params.py).
- Facility beds, OR tables, surgery durations, post-op holds, system labels (ERSS-/ERCS-type are labels only).
- Asset counts, speeds, ranges, litters, critical-care slots, turn times, basing.
- Threat envelopes, per-traversal loss probabilities, closure windows, casualty surge profiles.

## Modelling simplifications
- Loss probability applies per traversal of an active threat envelope (no kill-chain model).
- Assets return to their home base after each sortie; no en-route diversion or re-tasking.
- Planners see facility closures within +/-1 h of arrival (short foresight), not full future schedule.
- Role 1 beds are unlimited; Role 4 effectively so.
- Range rule: base->origin + origin->dest <= range, and dest->base <= range (refuel at destination). Strategic
  AE range assumes aerial refuelling.
- Hazard is piecewise-constant; death is the cumulative hazard reaching a per-patient Exp(1) draw.

## Result as first run (10-12 paired seeds, notional parameters)
| Scenario | Stovepipe | Joint | Optimized |
|---|---|---|---|
| Baseline | 0.405 | 0.208 | 0.192 |
| Surge 1.5x | 0.412 | 0.223 | 0.206 |
| No threats | 0.298 | 0.151 | 0.152 |
| 1 strategic AE | 0.406 | 0.224 | 0.219 |
(overall mortality fraction)
- The stovepipe-to-joint gap is large because stovepipe forbids any cross-service lift; its size depends
  entirely on that assumption and on the notional lift mix.
- Optimized beats joint by ~4 deaths/run in the contested baseline (paired CI excludes zero) but ties it
  with threats off: the gain comes from risk-aware routing and queue/capacity awareness, and it costs
  longer median time to Role 4 (~57 h vs ~48 h) because of fill-wait and batching.
- ~5% mortality is irreducible in this model (deaths before reaching Role 1).
