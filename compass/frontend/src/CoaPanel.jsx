function riskColor(risk) {
  if (risk >= 0.6) return "var(--status-closed)";
  if (risk >= 0.3) return "var(--status-contested)";
  return "var(--status-open)";
}

export default function CoaPanel({ stepData, loading, onHoverCoa }) {
  if (loading) {
    return (
      <div className="loading-scanline">
        <div className="loading-line">Running pipeline for this timestep…</div>
      </div>
    );
  }
  if (!stepData) {
    return <div className="loading-line">Select a timestep to run the pipeline.</div>;
  }

  const { candidate_coas: coas, risk_evaluations: riskEvals, selected_coa_id, decision_rationale } =
    stepData;

  const riskById = Object.fromEntries(riskEvals.map((r) => [r.coa_id, r]));

  return (
    <div key={stepData.step} className="fade-in">
      <div className="decision-card">
        <div className="decision-label">DECISION</div>
        <div className="decision-text">{decision_rationale}</div>
      </div>

      <div className="section-title">Candidate courses of action</div>
      {coas.map((coa) => {
        const risk = riskById[coa.coa_id];
        const riskPct = Math.round(coa.estimated_risk * 100);
        return (
          <div
            key={coa.coa_id}
            className={`coa-card ${coa.coa_id === selected_coa_id ? "selected" : ""}`}
            onMouseEnter={() => onHoverCoa?.(coa.affected_routes)}
            onMouseLeave={() => onHoverCoa?.([])}
          >
            <div className="coa-head">
              <span className="coa-id">{coa.coa_id}</span>
              <span className="coa-risk">{riskPct}%</span>
            </div>
            <div className="risk-bar-track">
              <div
                className="risk-bar-fill"
                style={{ width: `${riskPct}%`, background: riskColor(coa.estimated_risk) }}
              />
            </div>
            <div className="coa-desc">{coa.description}</div>
            {risk && <div className="coa-summary">{risk.tradeoff_summary}</div>}
          </div>
        );
      })}
    </div>
  );
}
