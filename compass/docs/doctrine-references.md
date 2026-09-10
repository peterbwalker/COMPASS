# Authoritative DoD Logistics Doctrine & TTP References for COMPASS

A working reference list for grounding the COMPASS agents (particularly
threat assessment, forecasting, and COA generation) in real DoD logistics
doctrine and contested-logistics concepts. All documents below are
unclassified and approved for public release.

---

## Tier 1 — Foundational concept & statutory definitions

These define *what* contested logistics means and *why* it's now a
first-order planning assumption — good grounding material for system
prompts across all agents.

- **Joint Concept for Contested Logistics (JCCL)** — Joint Staff J4, 2022.
  The keystone concept document; names and frames the problem this whole
  pipeline addresses. One of four supporting concepts under the Joint
  Warfighting Concept. Source: jcs.mil (Joint Staff J4).
- **10 U.S.C. § 2926** — statutory definition of "contested logistics
  environment." Useful as an authoritative, citable definition.
- **Joint Warfighting Concept (JWC)** — the parent concept JCCL supports;
  useful for higher-level operational context.

## Tier 2 — Joint doctrine (JP 4-0 series)

The core "how-to" doctrine for joint logistics. JP 4-0 is the keystone
document of the whole series.

| Publication | Title | Status |
|---|---|---|
| **JP 4-0** | Joint Logistics | Updated 2025 (keystone document) |
| **JP 4-09** | Joint Distribution Operations | Updated 2025 |
| **JP 4-08** | Logistics in Support of Multinational Operations | Updated 2025 |
| **JP 4-01** | Joint Doctrine for the Defense Transportation System | 2013 (check jcs.mil for updates) |
| **JP 4-01.6** | Joint Logistics Over-the-Shore (JLOTS) | 2005 |
| **JP 4-03** | Joint Bulk Petroleum and Water Doctrine | 2017 |
| **JP 4-04** | Contingency Basing | 2019 |
| **JP 4-05** | Joint Mobilization Planning | 2018 |
| **JP 4-10** | Operational Contract Support | 2019 |
| **JP 5-0** | Joint Planning | Updated 2025 |
| **JP 3-0** | Joint Operations | (operational context for logistics) |

Access point: **jcs.mil/Doctrine/Joint-Doctrine-Pubs/4-0-Logistics-Series/**
— the Joint Chiefs of Staff's official doctrine library. Also archived at
DTIC (apps.dtic.mil) and NPS's edocs mirror for older versions.

- **DoDI 5258.06** — Joint Deployment and Distribution Enterprise (JDDE),
  April 2020. Governs the enterprise-level distribution system JCCL and
  JP 4-09 operate within.

## Tier 3 — Service-specific doctrine

Each service has its own contested-logistics posture; useful if COMPASS
is meant to reflect a specific service's TTPs rather than purely joint
doctrine.

**Army**
- **FM 4-0, Sustainment Operations** (Aug 2024) — explicitly rewrites
  Army sustainment doctrine to *assume the supply chain is always
  contested* as a baseline planning assumption. Directly relevant to the
  threat-assessment and forecasting agents.
- **FM 3-0, Operations** — multi-domain operations context; FM 4-0 is
  nested under its framework.

**Marine Corps**
- **Installations and Logistics 2030** (Feb 2023) — Commandant-directed
  strategy document that explicitly refocuses USMC logistics on the
  contested logistics concept.
- Related: Expeditionary Advanced Base Operations (EABO) concept —
  distributed/contested basing context relevant to forward staging area
  modeling.

**Air Force**
- **AFDN 1-21, Agile Combat Employment (ACE)** (2021, updated) — the
  Air Force's operational scheme for dispersed, contested basing;
  explicitly addresses "logistics under attack" as a core enabling
  function. Source: doctrine.af.mil.
- **AFDP 3-0, Operations** (Jan 2025) — foundational doctrine that
  formally incorporates ACE into airpower employment doctrine.

**Navy** — no single equivalently-named capstone document surfaced in
this pass; Distributed Maritime Operations (DMO) is the closest
conceptual analog and worth a follow-up search if Navy-specific TTPs are
needed.

## Tier 4 — Studies & analysis (non-doctrinal, but authoritative context)

Useful for grounding *why* the pipeline's assumptions matter, and for
red-teaming scenario realism — not doctrine itself, but reputable
government/FFRDC analysis.

- **Defense Science Board Task Force on Survivable Logistics** (2018,
  executive summary unclassified) — assesses A2/AD threats to the Joint
  Logistics Enterprise; available via DTIC (apps.dtic.mil).
- **RAND**, *So Many Questions, So Little Time for Pacific Logistics*
  (2023) — commentary on intra-theater lift gaps in a Pacific contested
  scenario; useful for theater-specific realism if your synthetic
  scenarios stay Indo-Pacific-flavored.

---

## Suggested next step for actually using these

Doctrine PDFs aren't directly consumable by the agents as-is. The
practical path from here is building a small retrieval layer:

1. Pull the PDFs (all public, no access restrictions) into a local
   corpus.
2. Chunk and embed them (e.g., a simple vector store) so the
   COA-generation and risk-evaluation agents' system prompts can be
   grounded with retrieved doctrine excerpts relevant to the current
   forecast, rather than relying on the LLM's general training data.
3. Start narrow — JCCL + JP 4-0 + FM 4-0 cover the conceptual and Army
   TTP baseline well, and are a manageable starting corpus before adding
   the full JP 4-0 series and service-specific documents.

This would be a good next COMPASS component (a `retrieval_agent` or a
shared doctrine-lookup utility called by COA generation) if useful.
