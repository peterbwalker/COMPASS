"""Notional model parameters. NOT validated, NOT doctrine-sourced.

Replace with validated planning factors (e.g. from medical modelling and
simulation work) before drawing any conclusion from outputs.
"""
from __future__ import annotations

# Hazard rate (per hour) by acuity and highest care level received so far
# index: care level 0 (none) .. 4 (Role 4)
HAZARD_PER_H = {
    "IMM_SURG": [0.35, 0.12, 0.015, 0.004, 0.001],
    "IMM_MED":  [0.15, 0.05, 0.010, 0.003, 0.001],
    "DELAYED":  [0.030, 0.010, 0.004, 0.002, 0.0005],
    "MINIMAL":  [0.004, 0.002, 0.001, 0.0005, 0.0003],
}

DEFAULT_PARAMS = {
    "resus_factor": 0.6,          # hazard multiplier while awaiting surgery at a Role 2+ facility
    "on_table_factor": 0.35,      # hazard multiplier during surgery
    "crit_no_ccatt_mult": 1.6,    # hazard multiplier in transit for ICU-need patient w/o a critical-care slot
    "nonsurg_hold_r1_h": 0.25,
    "nonsurg_hold_r2_h": 1.0,
    "nonsurg_hold_r3_h": 6.0,
    "stay_r2_h": 24.0,            # bed occupancy of patients whose care ends at Role 2
    "stay_r3_h": 72.0,
    "tick_h": 0.25,
    "drain_h": 72.0,              # run past the casualty horizon to let the system drain
}

# Casualty attribute tables (notional)
ACUITY_MIX = {"IMM_SURG": 0.18, "IMM_MED": 0.10, "DELAYED": 0.32, "MINIMAL": 0.40}

# P(final_role) by acuity
FINAL_ROLE_MIX = {
    "IMM_SURG": {3: 0.35, 4: 0.65},
    "IMM_MED":  {3: 0.30, 4: 0.70},
    "DELAYED":  {2: 0.30, 3: 0.40, 4: 0.30},
    "MINIMAL":  {1: 0.75, 2: 0.25},
}
P_DCS = {"IMM_SURG": 1.0, "IMM_MED": 0.0, "DELAYED": 0.35, "MINIMAL": 0.0}
P_ICU = {"IMM_SURG": 0.5, "IMM_MED": 0.6, "DELAYED": 0.1, "MINIMAL": 0.0}
