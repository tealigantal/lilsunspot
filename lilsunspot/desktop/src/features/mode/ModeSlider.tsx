type ModeSliderProps = {
  label: string;
  left: string;
  right: string;
  value: number;
  onChange: (value: number) => void;
};

export function ModeSlider({ label, left, right, value, onChange }: ModeSliderProps) {
  return (
    <label className="modeSlider">
      <span>
        <strong>{label}</strong>
        <em>{value}</em>
      </span>
      <input type="range" min="0" max="100" value={value} onChange={(event) => onChange(Number(event.target.value))} />
      <small>
        <span>{left}</span>
        <span>{right}</span>
      </small>
    </label>
  );
}
