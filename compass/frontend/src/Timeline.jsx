import { useEffect, useState } from "react";

const SPEED_OPTIONS = [
  { label: "1x", intervalMs: 1800 },
  { label: "2x", intervalMs: 900 },
  { label: "4x", intervalMs: 450 },
];

export default function Timeline({ step, numSteps, onChange }) {
  const [playing, setPlaying] = useState(false);
  const [speedIdx, setSpeedIdx] = useState(0);

  // Auto-advance one step per tick while playing; stop at the end.
  useEffect(() => {
    if (!playing) return;
    const id = setInterval(() => {
      if (step >= numSteps - 1) {
        setPlaying(false);
        return;
      }
      onChange(step + 1);
    }, SPEED_OPTIONS[speedIdx].intervalMs);
    return () => clearInterval(id);
  }, [playing, speedIdx, step, numSteps, onChange]);

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
        onChange={(e) => {
          setPlaying(false);
          onChange(Number(e.target.value));
        }}
      />
      <div className="timeline-controls">
        <button
          className="play-button"
          onClick={() => setPlaying((p) => !p)}
          aria-label={playing ? "Pause" : "Play"}
        >
          {playing ? "⏸" : "▶"}
        </button>
        <div className="speed-toggle">
          {SPEED_OPTIONS.map((opt, i) => (
            <button
              key={opt.label}
              className={i === speedIdx ? "active" : ""}
              onClick={() => setSpeedIdx(i)}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
