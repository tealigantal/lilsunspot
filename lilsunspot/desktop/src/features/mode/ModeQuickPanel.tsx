import { useEffect, useMemo, useState } from "react";
import type { CurrentMode, ModeProfile } from "../../types";
import { getCurrentMode, getModes, selectMode } from "../../api";
import { StatusBadge } from "../../shared/components/StatusBadge";
import { ModeSlider } from "./ModeSlider";

type ModeQuickPanelProps = {
  onModeChanged?: (mode: CurrentMode) => void;
};

const PRESETS = [
  { id: "pragmatic", label: "务实" },
  { id: "balanced", label: "均衡" },
  { id: "emotional", label: "感性" }
];

export function modeName(modeId?: string) {
  const names: Record<string, string> = {
    default: "默认",
    pragmatic: "务实",
    balanced: "均衡",
    emotional: "感性"
  };
  return modeId ? names[modeId] || modeId : "默认";
}

export function ModeQuickPanel({ onModeChanged }: ModeQuickPanelProps) {
  const [modes, setModes] = useState<ModeProfile[]>([]);
  const [current, setCurrent] = useState<CurrentMode | null>(null);
  const [selectedMode, setSelectedMode] = useState("balanced");
  const [styleAxis, setStyleAxis] = useState(45);
  const [detailLevel, setDetailLevel] = useState(60);
  const [autonomyLevel, setAutonomyLevel] = useState(60);
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let mounted = true;
    async function load() {
      setBusy(true);
      try {
        const [modeList, mode] = await Promise.all([getModes(), getCurrentMode()]);
        if (!mounted) {
          return;
        }
        setModes(modeList);
        applyMode(mode.profile, mode.current);
        setCurrent(mode);
      } catch (error) {
        if (mounted) {
          setStatus(error instanceof Error ? error.message : "输出模式读取失败。");
        }
      } finally {
        if (mounted) {
          setBusy(false);
        }
      }
    }
    void load();
    return () => {
      mounted = false;
    };
  }, []);

  const selectedProfile = useMemo(
    () => modes.find((mode) => mode.id === selectedMode) || modes.find((mode) => mode.id === "balanced") || modes[0],
    [modes, selectedMode]
  );

  function applyMode(profile: ModeProfile, modeId = profile.id) {
    setSelectedMode(modeId);
    setStyleAxis(profile.style_axis);
    setDetailLevel(profile.detail_level);
    setAutonomyLevel(profile.autonomy_level);
  }

  async function choosePreset(modeId: string) {
    const profile = modes.find((item) => item.id === modeId);
    if (profile) {
      applyMode(profile, modeId);
    } else {
      setSelectedMode(modeId);
    }
  }

  async function save() {
    setBusy(true);
    setStatus("");
    try {
      const result = await selectMode(selectedMode, {
        style_axis: styleAxis,
        detail_level: detailLevel,
        autonomy_level: autonomyLevel
      });
      setCurrent(result);
      onModeChanged?.(result);
      setStatus(`已保存为${modeName(result.current)}输出模式。`);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "输出模式保存失败。");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="modeQuickPanel">
      <div className="settingsHeader">
        <div>
          <h3>输出模式</h3>
          <p>这不会阻断聊天，保存后下一条消息会使用新的回答偏好。</p>
        </div>
        <StatusBadge tone="ok">当前：{modeName(current?.current)}</StatusBadge>
      </div>
      <div className="presetRow">
        {PRESETS.map((preset) => (
          <button
            key={preset.id}
            type="button"
            className={selectedMode === preset.id ? "presetButton selected" : "presetButton"}
            onClick={() => void choosePreset(preset.id)}
          >
            {preset.label}
          </button>
        ))}
      </div>
      {selectedProfile && <p className="mutedText">{selectedProfile.description}</p>}
      <div className="sliderGrid">
        <ModeSlider label="表达风格" left="务实" right="感性" value={styleAxis} onChange={setStyleAxis} />
        <ModeSlider label="细节程度" left="简短" right="详细" value={detailLevel} onChange={setDetailLevel} />
        <ModeSlider label="自主程度" left="确认优先" right="自动推进" value={autonomyLevel} onChange={setAutonomyLevel} />
      </div>
      <div className="actionRow">
        <button type="button" onClick={save} disabled={busy || !selectedMode}>
          {busy ? "保存中" : "保存输出模式"}
        </button>
      </div>
      {status && <p className="inlineStatus">{status}</p>}
    </section>
  );
}
