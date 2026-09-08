# COMPASS

**C**ontested **O**perations **M**ulti-agent **P**lanning & **A**daptive **S**ustainment **S**ystem

COMPASS is a multi-agent, agentic pipeline for decision advantage in contested logistics. It fuses degraded/contested-environment signals, forecasts logistics network state, generates and evaluates courses of action (COAs), and surfaces auditable recommendations to a human decision-maker.

Supporting work for the NTSA 2026 talk: *"The Logistics Kill Chain: Agentic Pipelines for Decision Advantage in Contested Environments."*

## Architecture

COMPASS is built as a [LangGraph](https://github.com/langchain-ai/langgraph) state graph. Each pipeline stage is a node; the graph is explicit, traceable, and supports human-in-the-loop interrupts before any recommendation is finalized.

```
Sensing ──▶ Threat Assessment ──▶ Forecasting ──▶ COA Generation ──▶ Risk Evaluation ──▶ [HUMAN GATE] ──▶ Adjudication
                                        ▲                                                        │
                                        └────────────────── replan trigger ─────────────────────┘
```

See [`docs/architecture.md`](docs/architecture.md) for the full state schema and node-by-node design notes.

## Repository layout

```
compass/
├── src/
│   ├── agents/          # One module per pipeline agent
│   ├── orchestrator/    # LangGraph state schema + graph assembly
│   └── utils/           # Shared helpers (data loaders, logging, etc.)
├── notebooks/           # Colab-friendly prototyping notebooks
├── docs/                # Architecture notes, design decisions
└── tests/               # Unit tests per agent + graph integration tests
```

## Development workflow

1. **Prototype in Colab** — draft/test individual agent logic (especially the forecasting and COA-generation models) in `notebooks/`.
2. **Promote to `src/agents/`** — once an agent's logic stabilizes, lift it into a proper module with a clean function/class interface.
3. **Wire into the graph** — register the agent as a node in `src/orchestrator/graph.py`.
4. **Test** — add a unit test per agent and an integration test for any new graph path.

## Getting started

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m src.orchestrator.graph
```

## Status

Early scaffold — agent modules currently contain placeholder logic to validate the graph topology and state-passing contract. See `docs/architecture.md` for the build sequence.
