"""Data model for the COMPASS-MEDEVAC simulator.

Everything quantitative that ships with the default scenario is a NOTIONAL
PLACEHOLDER (see ASSUMPTIONS.md). The structures here are what matter: they are
meant to be overwritten with validated planning factors.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, List


class Service(str, Enum):
    ARMY = "ARMY"
    NAVY = "NAVY"
    USMC = "USMC"
    USAF = "USAF"
    JOINT = "JOINT"


class Mode(str, Enum):
    ROTARY = "ROTARY"
    TILTROTOR = "TILTROTOR"
    FIXED_WING = "FIXED_WING"      # tactical / intratheater aeromedical
    STRAT_AE = "STRAT_AE"          # strategic aeromedical evacuation
    SURFACE = "SURFACE"            # surface vessel lift


class Acuity(str, Enum):
    IMM_SURG = "IMM_SURG"   # immediate, needs damage-control surgery
    IMM_MED = "IMM_MED"     # immediate, non-surgical (airway, resp, burns...)
    DELAYED = "DELAYED"
    MINIMAL = "MINIMAL"


ACUITY_RANK = {Acuity.IMM_SURG: 0, Acuity.IMM_MED: 1, Acuity.DELAYED: 2, Acuity.MINIMAL: 3}


@dataclass
class Zone:
    id: str
    name: str
    lat: float
    lon: float
    r1_id: str
    tacevac_mean_h: float = 0.5   # point of injury -> Role 1 (ground / casualty collection)


@dataclass
class Facility:
    id: str
    name: str
    role: int                      # 1..4
    service: Service
    lat: float
    lon: float
    beds: int = 10
    or_tables: int = 0
    surgery_mean_h: float = 1.5
    postop_hold_h: float = 3.0     # minimum hold after surgery before onward move
    system_type: str = ""          # free text, e.g. "R2 resuscitative surgical (ERSS-type)"
    afloat: bool = False
    note: str = ""


@dataclass
class Base:
    id: str
    name: str
    lat: float
    lon: float


@dataclass
class AssetSpec:
    id: str
    name: str
    mode: Mode
    service: Service
    base_id: str
    speed_kmh: float
    range_km: float                # sortie rule: base->origin + origin->dest <= range; dest->base <= range
    litters: int
    crit_slots: int = 0            # patients that can receive critical-care en route (CCATT-type)
    turn_h: float = 0.5            # servicing / load+unload time (split across the sortie)


@dataclass
class ThreatWindow:
    id: str
    name: str
    lat: float
    lon: float
    radius_km: float
    start_h: float
    end_h: float
    loss_prob: Dict[str, float] = field(default_factory=dict)   # per traversal, by Mode value


@dataclass
class FacilityClosure:
    facility_id: str
    start_h: float
    end_h: float
    reason: str = ""


@dataclass
class CasualtyStream:
    zone_id: str
    start_h: float
    end_h: float
    rate_per_h: float
    service_mix: Dict[str, float]
    label: str = ""


@dataclass
class Scenario:
    name: str
    horizon_h: float
    seed: int
    zones: List[Zone]
    facilities: List[Facility]
    bases: List[Base]
    assets: List[AssetSpec]
    threats: List[ThreatWindow]
    closures: List[FacilityClosure]
    streams: List[CasualtyStream]
    params: Dict[str, float] = field(default_factory=dict)
    notional: bool = True

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PatientSpec:
    id: str
    service: Service
    zone_id: str
    t0: float
    acuity: Acuity
    final_role: int           # highest echelon of care the patient needs (1..4)
    needs_dcs: bool           # needs damage-control / resuscitative surgery
    needs_icu: bool           # needs critical care en route
    E: float                  # Exp(1) hazard threshold (common random number)
    tacevac_h: float
    surg_u: float             # uniform draw for surgery duration
