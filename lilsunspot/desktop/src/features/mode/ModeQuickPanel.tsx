import { useEffect, useState } from "react";
import type { ModeProfile } from "../../types";
import { StatusBadge } from "../../shared/components/StatusBadge";
import { useModeState } from "./ModeState";
import { ModeSlider } from "./ModeSlider";

const PRESETS = [
  { id: "pragmatic", label: "务实", tagline: "直接、少铺垫" },
  { id: "balanced", label: "均衡", tagline: "清楚、自然" },
  { id: "emotional", label: "感性", tagline: "温和、有陪伴感" }
];

export function modeName(modeId?: string) {
  const names: Record<string, string> = {
    pragmatic: "务实",
    balanced: "均衡",
    emotional: "感性",
    custom: "自定义"
  };
  return modeId ? names[modeId] || modeId : "均衡";
}

export function ModeQuickPanel({ conversationId = "" }: { conversationId?: string }) {
  const { modes, current, busy, status, saveMode, setStatus } = useModeState();
  const [selectedMode, setSelectedMode] = useState("balanced");
  const [styleAxis, setStyleAxis] = useState(45);

  useEffect(() => {
    if (current) {
      setSelectedMode(current.current);
      setStyleAxis(current.profile.style_axis);
    }
  }, [current]);

  function choosePreset(modeId: string) {
    const profile = modes.find((item) => item.id === modeId);
    setSelectedMode(modeId);
    if (profile) {
      setStyleAxis(profile.style_axis);
    }
  }

  async function save() {
    const fallback = current?.profile || modes.find((item) => item.id === "balanced");
    if (!fallback) {
      return;
    }
    const sliders: Pick<ModeProfile, "style_axis" | "detail_level" | "autonomy_level"> = {
      style_axis: styleAxis,
      detail_level: fallback.detail_level,
      autonomy_level: fallback.autonomy_level
    };
    setStatus("");
    try {
      const result = await saveMode(selectedMode, sliders, conversationId);
      setSelectedMode(result.current);
      setStyleAxis(result.profile.style_axis);
      setStatus(`已保存为${modeName(result.current)}表达风格。`);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "表达风格保存失败。");
    }
  }

  return (
    <details className="modeQuickPanel modeQuickPanelCompact expressionStylePanel">
      <summary>
        <span>
          <strong>表达风格</strong>
          <small>只影响措辞，不改变模型参数或权限</small>
        </span>
        <StatusBadge tone="ok">{modeName(current?.current)}</StatusBadge>
      </summary>
      <div className="presetRow presetCards">
        {PRESETS.map((preset) => (
          <button
            key={preset.id}
            type="button"
            className={selectedMode === preset.id ? "presetButton selected" : "presetButton"}
            onClick={() => choosePreset(preset.id)}
          >
            <strong>{preset.label}</strong>
            <span>{preset.tagline}</span>
          </button>
        ))}
      </div>
      <ModeSlider
        label="措辞风格"
        left="务实"
        right="感性"
        value={styleAxis}
        tone="cyan"
        onChange={(value) => {
          setSelectedMode("custom");
          setStyleAxis(value);
        }}
      />
      <div className="actionRow">
        <button type="button" onClick={() => void save()} disabled={busy}>{busy ? "保存中" : "保存表达风格"}</button>
      </div>
      {status && <p className="inlineStatus">{status}</p>}
    </details>
  );
}
