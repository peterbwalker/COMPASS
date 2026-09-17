export default function Timeline({ step, numSteps, onChange }) {
  return (
    <div className="timeline-block">
      <div className="label">
        <span>Timestep</span>
        <span className="value">
          {step} / {numSteps - 1}
        </span>
      </div>
      <input
        type="range"
        min={0}
        max={Math.max(numSteps - 1, 0)}
        value={step}
        onChange={(e) => onChange(Number(e.target.value))}
      />
    </div>
  );
}
