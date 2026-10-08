"""Notional INDOPACOM MEDEVAC scenario.

Geography is real (public city / island coordinates). Every capability, count,
capacity, speed and threat value is a NOTIONAL PLACEHOLDER chosen to make the
structure of the problem visible, not to represent any real force or plan.
"""
from __future__ import annotations

from typing import List

from .models import (
    AssetSpec, Base, CasualtyStream, Facility, FacilityClosure, Mode, Scenario,
    Service, ThreatWindow, Zone,
)

A, N, M, F = Service.ARMY, Service.NAVY, Service.USMC, Service.USAF


def _facilities(hospital_ship: bool) -> List[Facility]:
    fac = [
        # ---- Role 1 (one per POI zone) ----
        Facility("R1_BATANES", "R1 Batanes aid station", 1, M, 20.45, 121.97, beds=999),
        Facility("R1_NLUZON", "R1 N. Luzon aid station", 1, A, 18.30, 121.75, beds=999),
        Facility("R1_PALAWAN", "R1 Palawan aid station", 1, F, 9.80, 118.60, beds=999),
        Facility("R1_ISHIGAKI", "R1 Ishigaki aid station", 1, A, 24.35, 124.15, beds=999),
        Facility("R1_SAG", "R1 surface group (ship medical)", 1, N, 18.00, 117.50, beds=999, afloat=True),
        # ---- Role 2 resuscitative surgical (ERSS / ERCS-type, notional) ----
        Facility("R2_BATANES", "R2 Batanes", 2, M, 20.43, 121.98, beds=6, or_tables=1,
                 surgery_mean_h=1.5, postop_hold_h=3, system_type="R2 resuscitative surgical (ERSS-type)"),
        Facility("R2_NLUZON", "R2 Aparri", 2, A, 18.36, 121.64, beds=8, or_tables=1,
                 surgery_mean_h=1.5, postop_hold_h=3, system_type="R2 forward surgical team"),
        Facility("R2_LAOAG", "R2 Laoag", 2, F, 18.19, 120.60, beds=8, or_tables=1,
                 surgery_mean_h=1.5, postop_hold_h=3, system_type="R2 resuscitative surgical (ERSS-type)"),
        Facility("R2_PALAWAN", "R2 Puerto Princesa", 2, F, 9.74, 118.74, beds=8, or_tables=1,
                 surgery_mean_h=1.5, postop_hold_h=3, system_type="R2 resuscitative surgical (ERSS-type)"),
        Facility("R2_ISHIGAKI", "R2 Ishigaki", 2, A, 24.36, 124.18, beds=8, or_tables=2,
                 surgery_mean_h=1.5, postop_hold_h=3, system_type="R2 forward surgical team"),
        Facility("R2_ARG", "R2 afloat (amphibious ship)", 2, N, 19.80, 125.30, beds=20, or_tables=2,
                 surgery_mean_h=1.5, postop_hold_h=3, afloat=True, system_type="R2 afloat surgical"),
        # ---- Role 3 ----
        Facility("R3_OKINAWA", "R3 Okinawa", 3, N, 26.29, 127.79, beds=60, or_tables=4,
                 surgery_mean_h=2.0, postop_hold_h=12, system_type="R3 fixed hospital"),
        Facility("R3_CLARK", "R3 Clark expeditionary hospital", 3, F, 15.18, 120.57, beds=40, or_tables=3,
                 surgery_mean_h=2.0, postop_hold_h=12, system_type="R3 expeditionary hospital"),
        Facility("R3_GUAM", "R3 Guam", 3, N, 13.45, 144.78, beds=40, or_tables=3,
                 surgery_mean_h=2.0, postop_hold_h=12, system_type="R3 fixed hospital"),
        # ---- Role 4 ----
        Facility("R4_TRIPLER", "R4 Honolulu", 4, A, 21.36, -157.89, beds=500, or_tables=12,
                 system_type="R4 definitive care"),
        Facility("R4_MADIGAN", "R4 Pacific Northwest", 4, A, 47.10, -122.58, beds=300, or_tables=10,
                 system_type="R4 definitive care"),
        Facility("R4_SANDIEGO", "R4 San Diego", 4, N, 32.72, -117.15, beds=300, or_tables=10,
                 system_type="R4 definitive care"),
    ]
    if hospital_ship:
        fac.append(Facility("R3_SHIP", "R3 hospital ship (T-AH-class)", 3, N, 16.50, 123.50, beds=80,
                            or_tables=4, surgery_mean_h=2.0, postop_hold_h=12, afloat=True,
                            system_type="R3 afloat"))
    return fac


def _bases() -> List[Base]:
    return [
        Base("B_LAOAG", "Laoag airfield", 18.18, 120.53),
        Base("B_PALAWAN", "Puerto Princesa airfield", 9.74, 118.76),
        Base("B_ISHIGAKI", "Ishigaki airfield", 24.40, 124.19),
        Base("B_KADENA", "Kadena", 26.36, 127.77),
        Base("B_ANDERSEN", "Andersen", 13.58, 144.93),
        Base("B_CLARK", "Clark", 15.19, 120.56),
        Base("B_ARG", "Amphibious group (afloat)", 19.80, 125.30),
        Base("B_SUBIC", "Subic Bay", 14.79, 120.27),
    ]


def _assets(c17_count: int) -> List[AssetSpec]:
    a: List[AssetSpec] = []

    def add(prefix, n, name, mode, svc, base, speed, rng, lit, crit, turn):
        for i in range(n):
            a.append(AssetSpec(f"{prefix}{i+1}", f"{name} {i+1}", mode, svc, base, speed, rng, lit, crit, turn))

    # Army rotary (organic)
    a.append(AssetSpec("UH60_1", "Army MEDEVAC helo 1", Mode.ROTARY, A, "B_LAOAG", 240, 500, 6, 0, 0.4))
    a.append(AssetSpec("UH60_2", "Army MEDEVAC helo 2", Mode.ROTARY, A, "B_LAOAG", 240, 500, 6, 0, 0.4))
    a.append(AssetSpec("UH60_3", "Army MEDEVAC helo 3", Mode.ROTARY, A, "B_ISHIGAKI", 240, 500, 6, 0, 0.4))
    # USMC tiltrotor
    a.append(AssetSpec("MV22_1", "USMC tiltrotor 1", Mode.TILTROTOR, M, "B_LAOAG", 440, 1100, 8, 1, 0.5))
    a.append(AssetSpec("MV22_2", "USMC tiltrotor 2", Mode.TILTROTOR, M, "B_LAOAG", 440, 1100, 8, 1, 0.5))
    a.append(AssetSpec("MV22_3", "USMC tiltrotor 3", Mode.TILTROTOR, M, "B_ISHIGAKI", 440, 1100, 8, 1, 0.5))
    a.append(AssetSpec("MV22_4", "USMC tiltrotor 4", Mode.TILTROTOR, M, "B_KADENA", 440, 1100, 8, 1, 0.5))
    # Navy rotary
    a.append(AssetSpec("MH60S_1", "Navy helo 1", Mode.ROTARY, N, "B_ARG", 240, 500, 4, 1, 0.4))
    a.append(AssetSpec("MH60S_2", "Navy helo 2", Mode.ROTARY, N, "B_ARG", 240, 500, 4, 1, 0.4))
    a.append(AssetSpec("MH60S_3", "Navy helo 3", Mode.ROTARY, N, "B_ARG", 240, 500, 4, 1, 0.4))
    # USAF rescue helos
    a.append(AssetSpec("HH60_1", "USAF rescue helo 1", Mode.ROTARY, F, "B_PALAWAN", 260, 600, 4, 1, 0.4))
    a.append(AssetSpec("HH60_2", "USAF rescue helo 2", Mode.ROTARY, F, "B_LAOAG", 260, 600, 4, 1, 0.4))
    a.append(AssetSpec("HH60_3", "USAF rescue helo 3", Mode.ROTARY, F, "B_CLARK", 260, 600, 4, 1, 0.4))
    # USAF tactical aeromedical (C-130-class)
    a.append(AssetSpec("C130_1", "USAF tactical AE 1", Mode.FIXED_WING, F, "B_CLARK", 540, 3300, 24, 4, 1.0))
    a.append(AssetSpec("C130_2", "USAF tactical AE 2", Mode.FIXED_WING, F, "B_CLARK", 540, 3300, 24, 4, 1.0))
    a.append(AssetSpec("C130_3", "USAF tactical AE 3", Mode.FIXED_WING, F, "B_KADENA", 540, 3300, 24, 4, 1.0))
    a.append(AssetSpec("C130_4", "USAF tactical AE 4", Mode.FIXED_WING, F, "B_KADENA", 540, 3300, 24, 4, 1.0))
    # USAF strategic aeromedical (C-17-class, range assumes aerial refuelling)
    bases17 = ["B_KADENA", "B_KADENA", "B_ANDERSEN", "B_CLARK", "B_ANDERSEN"]
    for i in range(c17_count):
        a.append(AssetSpec(f"C17_{i+1}", f"USAF strategic AE {i+1}", Mode.STRAT_AE, F,
                           bases17[i % len(bases17)], 800, 11000, 36, 6, 2.0))
    # Navy surface lift
    a.append(AssetSpec("EPF_1", "Navy fast transport 1", Mode.SURFACE, N, "B_SUBIC", 65, 1800, 20, 0, 2.0))
    a.append(AssetSpec("EPF_2", "Navy fast transport 2", Mode.SURFACE, N, "B_SUBIC", 65, 1800, 20, 0, 2.0))
    return a


def _threats() -> List[ThreatWindow]:
    return [
        ThreatWindow("T_LUZON_STRAIT", "Luzon Strait A2/AD envelope", 20.8, 121.0, 220, 8, 96,
                     {"ROTARY": 0.05, "TILTROTOR": 0.04, "FIXED_WING": 0.06, "SURFACE": 0.03, "STRAT_AE": 0.02}),
        ThreatWindow("T_RYUKYU", "Ryukyu IADS envelope", 24.8, 125.3, 200, 20, 100,
                     {"ROTARY": 0.06, "TILTROTOR": 0.05, "FIXED_WING": 0.06, "SURFACE": 0.04, "STRAT_AE": 0.02}),
        ThreatWindow("T_SCS_MARITIME", "South China Sea maritime threat", 17.5, 118.5, 250, 0, 120,
                     {"ROTARY": 0.02, "TILTROTOR": 0.02, "FIXED_WING": 0.02, "SURFACE": 0.08}),
        ThreatWindow("T_KADENA_SALVO", "Kadena missile salvo window", 26.4, 127.8, 80, 30, 42,
                     {"ROTARY": 0.10, "TILTROTOR": 0.10, "FIXED_WING": 0.10, "SURFACE": 0.10, "STRAT_AE": 0.10}),
    ]


def _streams(surge: float) -> List[CasualtyStream]:
    def s(zone, a, b, rate, mix, label):
        return CasualtyStream(zone, a, b, rate * surge, mix, label)

    return [
        s("Z_BATANES", 0, 120, 0.25, {"USMC": .6, "ARMY": .3, "NAVY": .1}, "baseline"),
        s("Z_BATANES", 10, 22, 3.0, {"USMC": .6, "ARMY": .3, "NAVY": .1}, "assault surge"),
        s("Z_NLUZON", 0, 120, 0.20, {"ARMY": .55, "USMC": .25, "USAF": .2}, "baseline"),
        s("Z_NLUZON", 24, 40, 2.0, {"ARMY": .55, "USMC": .25, "USAF": .2}, "ground surge"),
        s("Z_PALAWAN", 0, 120, 0.10, {"USAF": .4, "ARMY": .3, "NAVY": .3}, "baseline"),
        s("Z_PALAWAN", 48, 60, 1.5, {"USAF": .4, "ARMY": .3, "NAVY": .3}, "airfield strike"),
        s("Z_ISHIGAKI", 0, 120, 0.20, {"ARMY": .5, "USMC": .4, "NAVY": .1}, "baseline"),
        s("Z_ISHIGAKI", 30, 44, 2.5, {"ARMY": .5, "USMC": .4, "NAVY": .1}, "island defense surge"),
        s("Z_SAG", 0, 120, 0.05, {"NAVY": 1.0}, "baseline"),
        s("Z_SAG", 14, 20, 4.0, {"NAVY": 0.9, "USMC": 0.1}, "ship strike"),
    ]


def build_scenario(surge_scale: float = 1.0, threats_on: bool = True, closures_on: bool = True,
                   c17_count: int = 3, hospital_ship: bool = True, seed: int = 1,
                   horizon_h: float = 120.0) -> Scenario:
    zones = [
        Zone("Z_BATANES", "Batanes (Luzon Strait)", 20.45, 121.97, "R1_BATANES", 0.6),
        Zone("Z_NLUZON", "Northern Luzon", 18.30, 121.75, "R1_NLUZON", 0.5),
        Zone("Z_PALAWAN", "Palawan", 9.80, 118.60, "R1_PALAWAN", 0.5),
        Zone("Z_ISHIGAKI", "Ishigaki (Ryukyus)", 24.35, 124.15, "R1_ISHIGAKI", 0.5),
        Zone("Z_SAG", "Surface action group (SCS)", 18.00, 117.50, "R1_SAG", 0.3),
    ]
    closures = []
    if closures_on:
        closures = [
            FacilityClosure("R3_OKINAWA", 32, 44, "ramp / runway damage, notional"),
            FacilityClosure("R2_PALAWAN", 55, 75, "airfield strike, notional"),
        ]
    return Scenario(
        name="INDOPACOM notional MEDEVAC (POI to Role 4)",
        horizon_h=horizon_h, seed=seed, zones=zones,
        facilities=_facilities(hospital_ship), bases=_bases(), assets=_assets(c17_count),
        threats=_threats() if threats_on else [], closures=closures,
        streams=_streams(surge_scale),
    )
