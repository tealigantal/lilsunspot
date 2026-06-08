import { useEffect, useMemo, useState } from "react";
import type { CurrentMode, ModeProfile } from "../../types";
import { getCurrentMode, getModes, selectMode } from "../../api";
import { StatusBadge } from "../../shared/components/StatusBadge";
import { ModeSlider } from "./ModeSlider";

type ModeQuickPanelProps = {
  variant?: "compact" | "page";
  onModeChanged?: (mode: CurrentMode) => void;
};

const PRESETS = [
  { id: "pragmatic", label: "务实", tagline: "先结论，再步骤" },
  { id: "balanced", label: "均衡", tagline: "有解释，但不啰嗦" },
  { id: "emotional", label: "感性", tagline: "先承接，再建议" }
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

function previewCopy(modeId: string, styleAxis: number, detailLevel: number, autonomyLevel: number) {
  if (modeId === "pragmatic" || (styleAxis < 40 && autonomyLevel < 55)) {
    return [
      "先锁定最小可运行链路：本地服务、模型配置、桌面聊天。",
      "第一步不要做插件市场或复杂主题，先让 Windows 上能启动、能配置 Key、能发出第一条消息。",
      detailLevel > 65 ? "完成后再接输出模式和微信命令，避免主路径没稳就扩展入口。" : "主路径跑通后再加模式和微信。"
    ];
  }
  if (modeId === "emotional" || styleAxis > 68) {
    return [
      "先把目标压小：做一个能每天打开、能帮你推进任务的个人 agent。",
      "第一步从本机启动和模型设置开始，因为这会决定普通用户能不能真的用起来。",
      autonomyLevel > 65 ? "我会直接列出下一步清单，并把需要确认的地方单独拎出来。" : "你确认方向后，再继续加微信和审批。"
    ];
  }
  return [
    "先做最小闭环：本地 daemon、Provider 保存、桌面聊天。",
    "再把输出模式接入系统提示，让回答风格可控。",
    detailLevel > 55 ? "最后补微信命令、安全审批和诊断导出，保证每个入口都能解释清楚当前状态。" : "最后补微信、审批和诊断。"
  ];
}

export function ModeQuickPanel({ variant = "page", onModeChanged }: ModeQuickPanelProps) {
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
        onModeChanged?.(mode);
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
  const preview = useMemo(
    () => previewCopy(selectedMode, styleAxis, detailLevel, autonomyLevel),
    [selectedMode, styleAxis, detailLevel, autonomyLevel]
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
    <section className={`modeQuickPanel ${variant === "compact" ? "modeQuickPanelCompact" : "modeQuickPanelPage"}`}>
      <div className="settingsHeader modeHeader">
        <div>
          <h3>{variant === "compact" ? "模式混音器" : "输出模式不是设置页，是回答风格的调音台"}</h3>
          <p>{variant === "compact" ? "下一条消息会使用这个偏好。" : "拖动后立即看到预览；保存后下一条桌面聊天和微信私聊都生效。"}</p>
        </div>
        <StatusBadge tone="ok">{variant === "compact" ? modeName(current?.current) : `当前：${modeName(current?.current)}`}</StatusBadge>
      </div>
      <div className="presetRow presetCards">
        {PRESETS.map((preset) => (
          <button
            key={preset.id}
            type="button"
            className={selectedMode === preset.id ? "presetButton selected" : "presetButton"}
            onClick={() => void choosePreset(preset.id)}
          >
            <strong>{preset.label}</strong>
            {variant === "page" && <span>{preset.tagline}</span>}
            {current?.current === preset.id && <em>当前</em>}
          </button>
        ))}
      </div>
      <div className="modeMixerBody">
        <div className="sliderGrid">
          <ModeSlider label="唱 / 表达" left="务实" right="感性" value={styleAxis} tone="cyan" onChange={setStyleAxis} />
          <ModeSlider label="RAP / 细节" left="简短" right="详细" value={detailLevel} tone="yellow" onChange={setDetailLevel} />
          <ModeSlider label="篮球 / 自主" left="确认" right="推进" value={autonomyLevel} tone="orange" onChange={setAutonomyLevel} />
        </div>
        {variant === "page" && (
          <aside className="modePreviewPanel">
            <h3>实时预览</h3>
            <span>固定测试问题</span>
            <strong>我想做一个个人 agent，第一步怎么做？</strong>
            <div>
              <em>{modeName(selectedMode)}模式输出示例</em>
              {preview.map((line) => (
                <p key={line}>{line}</p>
              ))}
            </div>
          </aside>
        )}
      </div>
      {selectedProfile && variant === "page" && <p className="mutedText">{selectedProfile.description}</p>}
      <div className="actionRow">
        <button type="button" onClick={save} disabled={busy || !selectedMode}>
          {busy ? "保存中" : "保存输出模式"}
        </button>
      </div>
      {status && <p className="inlineStatus">{status}</p>}
    </section>
  );
}
