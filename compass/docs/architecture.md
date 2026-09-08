# COMPASS Architecture

## Pipeline stages (LangGraph nodes)

| Node | Agent | Input keys | Output keys |
|---|---|---|---|
| `sensing` | `sensing_agent` | `raw_feeds` | `logistics_snapshot` |
| `threat_assessment` | `threat_assessment_agent` | `logistics_snapshot` | `threat_assessment` |
| `forecasting` | `forecasting_agent` | `logistics_snapshot`, `threat_assessment` | `forecast` |
| `coa_generation` | `coa_generation_agent` | `forecast` | `candidate_coas` |
| `risk_evaluation` | `risk_evaluation_agent` | `candidate_coas` | `risk_evaluations` |
| `adjudication` | `adjudication_agent` | `candidate_coas`, `risk_evaluations` | `selected_coa_id`, `decision_rationale`, `human_decision` |

## Human-in-the-loop gate

The graph is compiled with `interrupt_before=["adjudication"]`. This means execution pauses after `risk_evaluation` and before a decision is recorded, so a human reviewer can:

- Inspect `candidate_coas` and `risk_evaluations`
- Approve, reject, or request alternatives (`human_decision`)
- Trigger a replan (`replan_requested = True`) which routes back to `forecasting`

This is the node to build a real UI/CLI review step around — see `route_after_risk_evaluation` in `src/orchestrator/graph.py`.

## Why LangGraph

- **Explicit control flow.** Every transition is a defined edge, not emergent agent negotiation — important for explainability to a DoD/IC audience.
- **Native interrupt/resume.** Human adjudication is a first-class pattern, not bolted on.
- **Traceable state.** The full `CompassState` at each node is inspectable — this becomes the audit trail.
- **Self-hostable.** No required external service dependency, which matters for eventual on-prem/classified deployment.

## Model placement (which agents need what kind of model)

| Agent | Model type | Notes |
|---|---|---|
| Sensing | Data fusion / normalization logic | Likely rules + parsers rather than an LLM |
| Threat Assessment | Classifier / fused reporting model | Candidate for a trained model on historical denial data |
| Forecasting | Time-series / graph-based prediction | **Primary Colab prototyping target** |
| COA Generation | Hybrid: LLM (narrative/option generation) + solver (feasibility/cost) | LLM proposes, solver validates |
| Risk Evaluation | Scoring function + LLM-generated tradeoff narrative | Could incorporate commander's-intent embeddings |
| Adjudication | Human interface layer | No model — presentation + audit logging |

## Build sequence

1. Validate graph topology and state-passing contract with current stub agents (done — see `src/orchestrator/graph.py` smoke test).
2. Prototype the forecasting model in `notebooks/` against synthetic or open logistics data.
3. Promote forecasting model into `src/agents/forecasting_agent.py`.
4. Repeat for threat assessment and COA generation.
5. Wire a real human review interface around the `interrupt_before` gate.
6. Add integration tests covering the replan loop.

## Open questions

- Data source for realistic contested-logistics scenarios (synthetic generator vs. existing wargame/simulation dataset).
- Whether COA generation's LLM component should call an external API or a locally hosted model (relevant for classified deployment).
- Metrics for "decision advantage" to use as a demo/evaluation criterion for the NTSA talk.
