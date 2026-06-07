import type { CurrentMode } from "../../types";
import { ModeQuickPanel } from "./ModeQuickPanel";

type ModeSettingsProps = {
  onModeChanged?: (mode: CurrentMode) => void;
};

export function ModeSettings({ onModeChanged }: ModeSettingsProps) {
  return <ModeQuickPanel onModeChanged={onModeChanged} />;
}
