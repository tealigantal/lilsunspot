import { useEffect, useState } from "react";
import {
  getCurrentGenerationControl,
  getGenerationModes,
  selectGenerationControl
} from "../../api";
import type {
  GenerationControl,
  GenerationMode,
  GenerationParameterDetail,
  GenerationParameterValue,
  GenerationSelection
} from "../../types";
import { StatusBadge } from "../../shared/components/StatusBadge";

type GenerationScope = "global" | "conversation" | "turn";

type GenerationControlPanelProps = {
  conversationId: string;
  turnOverride: GenerationSelection | null;
  onTurnOverrideChange: (selection: GenerationSelection | null) => void;
};

const ADVANCED_FIELDS = [
  { key: "temperature", label: "temperature", kind: "number", step: "0.05" },
  { key: "top_p", label: "top-p", kind: "number", step: "0.05" },
  { key: "max_tokens", label: "最大输出", kind: "number", step: "100" },
  { key: "reasoning_effort", label: "推理强度", kind: "reasoning", step: "" },
  { key: "max_iterations", label: "最大行动次数", kind: "number", step: "1" }
] as const;

function inputValue(value: GenerationParameterValue | undefined) {
  return value === null || value === undefined ? "" : String(value);
}

function parseFieldValue(key: string, value: string): GenerationParameterValue {
  if (!value) {
    return null;
  }
  if (key === "reasoning_effort") {
    return value;
  }
  return Number(value);
}

function detailSummary(detail: GenerationParameterDetail | undefined) {
  if (!detail) {
    return "等待模型能力信息";
  }
  const parts = [detail.source_label, detail.status === "default" ? "模型默认" : detail.status];
  if (detail.range) {
    parts.push(`${detail.range.min}–${detail.range.max}`);
  }
  if (detail.default !== null && detail.default !== undefined) {
    parts.push(`默认 ${detail.default}`);
  }
  return parts.join(" · ");
}

export function GenerationControlPanel({
  conversationId,
  turnOverride,
  onTurnOverrideChange
}: GenerationControlPanelProps) {
  const [modes, setModes] = useState<GenerationMode[]>([]);
  const [control, setControl] = useState<GenerationControl | null>(null);
  const [scope, setScope] = useState<GenerationScope>("conversation");
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("");

  useEffect(() => {
    let cancelled = false;
    setBusy(true);
    setStatus("");
    Promise.all([getGenerationModes(), getCurrentGenerationControl(conversationId)])
      .then(([nextModes, nextControl]) => {
        if (cancelled) {
          return;
        }
        setModes(nextModes);
        setControl(nextControl);
        setDraft(
          Object.fromEntries(
            ADVANCED_FIELDS.map((field) => [field.key, inputValue(nextControl.requested_parameters[field.key])])
          )
        );
      })
      .catch((error) => {
        if (!cancelled) {
          setStatus(error instanceof Error ? error.message : "生成控制读取失败。");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setBusy(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [conversationId]);

  async function applySelection(selection: GenerationSelection) {
    setBusy(true);
    setStatus("");
    try {
      const result = await selectGenerationControl(selection, {
        conversationId,
        scope
      });
      setControl(result);
      if (scope === "turn") {
        onTurnOverrideChange(selection);
        setStatus("已设置为仅下一条消息使用。");
      } else {
        onTurnOverrideChange(null);
        setStatus(scope === "global" ? "已保存为全局默认。" : "已保存到当前会话。");
      }
      return true;
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "生成模式保存失败。");
      return false;
    } finally {
      setBusy(false);
    }
  }

  async function saveAdvanced() {
    const parameters = Object.fromEntries(
      ADVANCED_FIELDS.map((field) => [field.key, parseFieldValue(field.key, draft[field.key] || "")])
    );
    await applySelection({ mode: "custom", parameters });
  }

  async function restoreDefaults() {
    const parameters = {
      temperature: null,
      top_p: null,
      top_k: null,
      max_tokens: null,
      reasoning_effort: null,
      max_iterations: null,
      seed: null
    };
    const restored = await applySelection({ mode: "custom", parameters });
    if (restored) {
      setDraft(Object.fromEntries(ADVANCED_FIELDS.map((field) => [field.key, ""])));
      setStatus("已恢复模型默认值；这些字段将在请求中省略。");
    }
  }

  return (
    <section className="generationControlPanel" aria-label="生成控制">
      <div className="settingsHeader modeHeader">
        <div>
          <h3>生成控制</h3>
          <p>真实影响模型稳定性、长度、思考和行动预算。</p>
        </div>
        <StatusBadge tone={control?.fully_supported ? "ok" : "warning"}>
          {control?.fully_supported ? "完整支持" : "部分支持"}
        </StatusBadge>
      </div>

      <div className="generationScope" aria-label="设置作用范围">
        <button type="button" className={scope === "conversation" ? "selected" : ""} onClick={() => setScope("conversation")}>当前会话</button>
        <button type="button" className={scope === "turn" ? "selected" : ""} onClick={() => setScope("turn")}>仅下一条</button>
        <button type="button" className={scope === "global" ? "selected" : ""} onClick={() => setScope("global")}>全局默认</button>
      </div>

      <div className="generationModeGrid">
        {modes.map((mode) => (
          <button
            key={mode.id}
            type="button"
            className={control?.mode === mode.id ? "generationMode selected" : "generationMode"}
            onClick={() => void applySelection({ mode: mode.id })}
            disabled={busy}
          >
            <strong>{mode.label}</strong>
            <span>{mode.description}</span>
          </button>
        ))}
      </div>

      {control && (
        <div className="generationSummary">
          <strong>{control.label}</strong>
          <span>{control.compatibility_summary}</span>
          <dl>
            <div><dt>稳定性</dt><dd>{control.effects.stability || "模型默认"}</dd></div>
            <div><dt>长度</dt><dd>{control.effects.length || "模型默认"}</dd></div>
            <div><dt>思考</dt><dd>{control.effects.reasoning || "模型默认"}</dd></div>
            <div><dt>主动执行</dt><dd>{control.effects.autonomy || "模型默认"}</dd></div>
          </dl>
          <small>{control.provider} / {control.model}</small>
        </div>
      )}

      <details className="generationAdvanced" open={advancedOpen} onToggle={(event) => setAdvancedOpen(event.currentTarget.open)}>
        <summary>高级设置</summary>
        <div className="generationFieldList">
          {ADVANCED_FIELDS.map((field) => {
            const detail = control?.parameters[field.key];
            return (
              <label key={field.key}>
                <span><b>{field.label}</b><small>{detailSummary(detail)}</small></span>
                {field.kind === "reasoning" ? (
                  <select value={draft[field.key] || ""} onChange={(event) => setDraft((current) => ({ ...current, [field.key]: event.target.value }))}>
                    <option value="">模型默认</option>
                    <option value="none">不启用</option>
                    <option value="low">低</option>
                    <option value="medium">中</option>
                    <option value="high">高</option>
                    <option value="max">最高</option>
                  </select>
                ) : (
                  <input
                    type="number"
                    value={draft[field.key] || ""}
                    step={field.step}
                    min={detail?.range?.min}
                    max={detail?.range?.max}
                    placeholder="模型默认"
                    onChange={(event) => setDraft((current) => ({ ...current, [field.key]: event.target.value }))}
                  />
                )}
                {detail?.reason && <em>{detail.reason}</em>}
              </label>
            );
          })}
        </div>
        <div className="actionRow generationActions">
          <button type="button" className="secondaryButton" onClick={() => void restoreDefaults()} disabled={busy}>恢复模型默认值</button>
          <button type="button" onClick={() => void saveAdvanced()} disabled={busy}>{busy ? "保存中" : "保存自定义"}</button>
        </div>
      </details>

      {turnOverride && <p className="inlineStatus">下一条消息有单轮覆盖，发送后自动清除。</p>}
      {status && <p className="inlineStatus" aria-live="polite">{status}</p>}
    </section>
  );
}
