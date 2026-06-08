import type { CSSProperties } from "react";

type ModeSliderProps = {
  label: string;
  left: string;
  right: string;
  value: number;
  tone?: "cyan" | "yellow" | "orange";
  onChange: (value: number) => void;
};

const TONE_COLORS = {
  cyan: "#63f6da",
  yellow: "#ffd552",
  orange: "#ff8b24"
};

export function ModeSlider({ label, left, right, value, tone = "cyan", onChange }: ModeSliderProps) {
  const style = { "--slider-value": `${value}%`, "--slider-color": TONE_COLORS[tone] } as CSSProperties;
  return (
    <label className="modeSlider">
      <span>
        <strong>{label}</strong>
        <em>{value}</em>
      </span>
      <input
        type="range"
        min="0"
        max="100"
        value={value}
        style={style}
        onChange={(event) => onChange(Number(event.target.value))}
      />
      <small>
        <span>{left}</span>
        <span>{right}</span>
      </small>
    </label>
  );
}
