import { useEffect, useMemo, useState } from "react";
import type { ModeProfile } from "../../types";
import { StatusBadge } from "../../shared/components/StatusBadge";
import { useModeState } from "./ModeState";
import { ModeSlider } from "./ModeSlider";

const PRESETS = [
  { id: "pragmatic", label: "务实", tagline: "先结论，再步骤" },
  { id: "balanced", label: "均衡", tagline: "有解释，但不啰嗦" },
  { id: "emotional", label: "感性", tagline: "先承接，再建议" },
  { id: "custom", label: "自定义", tagline: "手动滑杆组合" }
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
      autonomyLevel > 65 ? "我会直接列出下一步清单，并把需要确认的地方单独拎出来。" : "你确认方向后，再继续加微信。"
    ];
  }
  return [
    "先做最小闭环：本地 daemon、Provider 保存、桌面聊天。",
    "再把输出模式接入系统提示，让回答风格可控。",
    detailLevel > 55 ? "最后补微信连接和文件同步，保证每个入口都能解释清楚当前状态。" : "最后补微信连接。"
  ];
}

function sliderSummary(styleAxis: number, detailLevel: number, autonomyLevel: number) {
  const style = styleAxis <= 35 ? "表达更务实" : styleAxis >= 70 ? "表达更有陪伴感" : "表达平衡清楚";
  const detail = detailLevel <= 35 ? "回答保持简短" : detailLevel >= 70 ? "回答给出更充分细节" : "回答详略适中";
  const autonomy =
    autonomyLevel <= 35
      ? "风险或不确定时优先确认"
      : autonomyLevel >= 70
        ? "可自动推进明确的下一步"
        : "在自动推进和必要确认之间保持平衡";
  return `${style}；${detail}；${autonomy}。`;
}

export function ModeQuickPanel() {
  const { modes, current, busy, status, saveMode, setStatus } = useModeState();
  const [selectedMode, setSelectedMode] = useState("balanced");
  const [styleAxis, setStyleAxis] = useState(45);
  const [detailLevel, setDetailLevel] = useState(60);
  const [autonomyLevel, setAutonomyLevel] = useState(60);

  useEffect(() => {
    if (!current) {
      return;
    }
    applyMode(current.profile, current.current);
  }, [current?.current, current?.profile.style_axis, current?.profile.detail_level, current?.profile.autonomy_level]);

  const selectedProfile = useMemo(
    () => modes.find((mode) => mode.id === selectedMode) || modes.find((mode) => mode.id === "balanced") || modes[0],
    [modes, selectedMode]
  );
  const preview = useMemo(
    () => previewCopy(selectedMode, styleAxis, detailLevel, autonomyLevel),
    [selectedMode, styleAxis, detailLevel, autonomyLevel]
  );
  const localSliderSummary = useMemo(() => sliderSummary(styleAxis, detailLevel, autonomyLevel), [styleAxis, detailLevel, autonomyLevel]);
  const promptLayers = useMemo(
    () =>
      (current?.prompt?.layers || []).map((layer) => {
        if (layer.id === "mode_profile") {
          return { ...layer, summary: selectedProfile?.description || layer.summary };
        }
        if (layer.id === "slider_overrides") {
          return { ...layer, summary: localSliderSummary };
        }
        return layer;
      }),
    [current?.prompt?.layers, localSliderSummary, selectedProfile?.description]
  );

  function applyMode(profile: ModeProfile, modeId = profile.id) {
    setSelectedMode(modeId);
    setStyleAxis(profile.style_axis);
    setDetailLevel(profile.detail_level);
    setAutonomyLevel(profile.autonomy_level);
  }

  function choosePreset(modeId: string) {
    const profile =
      modeId === "custom"
        ? current?.profile || modes.find((item) => item.id === "custom") || modes.find((item) => item.id === "balanced")
        : modes.find((item) => item.id === modeId);
    if (profile) {
      applyMode(profile, modeId);
    } else {
      setSelectedMode(modeId);
    }
  }

  function updateCustomSlider(key: "style_axis" | "detail_level" | "autonomy_level", value: number) {
    setSelectedMode("custom");
    if (key === "style_axis") {
      setStyleAxis(value);
    } else if (key === "detail_level") {
      setDetailLevel(value);
    } else {
      setAutonomyLevel(value);
    }
  }

  async function save() {
    setStatus("");
    try {
      const result = await saveMode(selectedMode, {
        style_axis: styleAxis,
        detail_level: detailLevel,
        autonomy_level: autonomyLevel
      });
      applyMode(result.profile, result.current);
      setStatus(`已保存为${modeName(result.current)}输出模式。`);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "输出模式保存失败。");
    }
  }

  return (
    <section className="modeQuickPanel modeQuickPanelCompact">
      <div className="settingsHeader modeHeader">
        <div>
          <h3>模式混音器</h3>
          <p>下一条消息会使用这个偏好。</p>
        </div>
        <StatusBadge tone="ok">{modeName(current?.current)}</StatusBadge>
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
            <span>{preset.tagline}</span>
            {current?.current === preset.id && <em>当前</em>}
          </button>
        ))}
      </div>
      <div className="modeMixerBody">
        <div className="sliderGrid">
          <ModeSlider
            label="风格 / 表达"
            left="务实"
            right="感性"
            value={styleAxis}
            tone="cyan"
            onChange={(value) => updateCustomSlider("style_axis", value)}
          />
          <ModeSlider
            label="长度 / 细节"
            left="简短"
            right="详细"
            value={detailLevel}
            tone="yellow"
            onChange={(value) => updateCustomSlider("detail_level", value)}
          />
          <ModeSlider
            label="确认 / 自主"
            left="确认"
            right="推进"
            value={autonomyLevel}
            tone="orange"
            onChange={(value) => updateCustomSlider("autonomy_level", value)}
          />
        </div>
      </div>
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
        {promptLayers.length > 0 && (
          <ul className="modePromptLayers" aria-label="Prompt 编译层">
            {promptLayers.map((layer) => (
              <li key={layer.id}>
                <b>{layer.label}</b>
                <span>{layer.summary}</span>
              </li>
            ))}
          </ul>
        )}
        <p className="modeSliderSummary">当前滑杆：{localSliderSummary}</p>
        <div className="actionRow modePreviewActions">
          <button type="button" onClick={save} disabled={busy || !selectedMode}>
            {busy ? "保存中" : "保存输出模式"}
          </button>
        </div>
      </aside>
      {status && <p className="inlineStatus">{status}</p>}
    </section>
  );
}
