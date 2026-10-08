export default function ModeSwitch({ mode, onChange }) {
  return (
    <div className="mv-modeswitch" role="tablist">
      <button role="tab" aria-selected={mode === "logistics"} className={mode === "logistics" ? "on" : ""} onClick={() => onChange("logistics")}>Logistics</button>
      <button role="tab" aria-selected={mode === "medevac"} className={mode === "medevac" ? "on" : ""} onClick={() => onChange("medevac")}>MEDEVAC</button>
    </div>
  );
}
