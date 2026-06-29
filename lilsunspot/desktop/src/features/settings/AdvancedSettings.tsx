import { useEffect, useState } from "react";
import { exportAdvancedConfig, getAdvancedExtensions, importAdvancedConfig, updateProductCapability } from "../../api";
import type { AdvancedConfigExport, AdvancedExtensions } from "../../types";
import { StatusBadge } from "../../shared/components/StatusBadge";
import { TechnicalDetails } from "../../shared/components/TechnicalDetails";

export function AdvancedSettings() {
  const [data, setData] = useState<AdvancedExtensions | null>(null);
  const [exportData, setExportData] = useState<AdvancedConfigExport | null>(null);
  const [importText, setImportText] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  async function load() {
    setBusy(true);
    setMessage("");
    try {
      setData(await getAdvancedExtensions());
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "高级扩展状态读取失败。");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function toggleToolset(toolsetId: string, enabled: boolean) {
    setBusy(true);
    setMessage("");
    try {
      const capability = await updateProductCapability(toolsetId, enabled);
      setData((current) =>
        current
          ? {
              ...current,
              toolsets: current.toolsets.map((item) =>
                item.id === capability.id ? { ...item, enabled: capability.enabled } : item
              )
            }
          : current
      );
      setMessage("能力开关已保存。");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "能力开关保存失败。");
    } finally {
      setBusy(false);
    }
  }

  async function exportConfig() {
    setBusy(true);
    setMessage("");
    try {
      const exported = await exportAdvancedConfig();
      setExportData(exported);
      setImportText(JSON.stringify(exported, null, 2));
      setMessage("已生成脱敏配置。");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "脱敏配置导出失败。");
    } finally {
      setBusy(false);
    }
  }

  async function importConfig() {
    setBusy(true);
    setMessage("");
    try {
      const parsed = JSON.parse(importText) as Record<string, unknown>;
      const result = await importAdvancedConfig(parsed);
      setMessage(
        `${result.message} 能力 ${result.applied.capabilities} 项，任务 ${result.applied.tasks} 项，Profile ${result.applied.profiles} 项。`
      );
      await load();
    } catch (error) {
      setMessage(error instanceof SyntaxError ? "配置内容不是有效 JSON。" : error instanceof Error ? error.message : "配置导入失败。");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="settingsSection advancedProductSettings">
      <div className="settingsHeader">
        <div>
          <h3>高级</h3>
          <p>高级扩展提供受保护的产品层导入/导出；插件安装、raw env 编辑、终端工具默认不开放。</p>
        </div>
        <StatusBadge tone={data?.dangerous_actions_enabled ? "danger" : "neutral"}>
          {data?.mode || "只读"}
        </StatusBadge>
      </div>

      <div className="controlPanelGrid">
        <article className="controlPanelCard">
          <h4>Skills</h4>
          <strong>{data?.skills.count ?? 0} 个</strong>
          <p>{data?.skills.available ? (data.skills.items.slice(0, 6).join("、") || "未发现可展示项") : "当前仓库未发现 skills 目录。"}</p>
        </article>
        <article className="controlPanelCard">
          <h4>Plugins</h4>
          <strong>{data?.plugins.count ?? 0} 个</strong>
          <p>{data?.plugins.available ? (data.plugins.items.slice(0, 6).join("、") || "未发现可展示项") : "当前仓库未发现 plugins 目录。"}</p>
        </article>
      </div>

      <article className="controlPanelCard">
        <h4>能力开关</h4>
        <div className="capabilitySwitchGrid">
          {(data?.toolsets || []).map((toolset) => (
            <label key={toolset.id} className="capabilitySwitch">
              <input
                type="checkbox"
                checked={toolset.enabled}
                disabled={busy}
                onChange={(event) => void toggleToolset(toolset.id, event.target.checked)}
              />
              <span>
                <strong>{toolset.label}</strong>
                <em>{toolset.enabled ? "已启用" : "未启用"}</em>
                <small>{toolset.requires_approval ? "需要安全确认" : "普通能力"}</small>
              </span>
            </label>
          ))}
        </div>
      </article>

      <article className="controlPanelCard advancedConfigPanel">
        <h4>脱敏配置导出 / 安全导入</h4>
        <p>导出不会包含 API Key、runtime token、微信凭据、聊天正文或附件原文；导入只写入产品层能力、任务和 Profile。</p>
        <div className="actionRow">
          <button type="button" className="secondaryButton compactButton" onClick={() => void exportConfig()} disabled={busy}>
            生成脱敏配置
          </button>
          <button type="button" className="secondaryButton compactButton" onClick={() => void importConfig()} disabled={busy || !importText.trim()}>
            导入产品设置
          </button>
        </div>
        <textarea
          value={importText}
          onChange={(event) => setImportText(event.target.value)}
          placeholder="粘贴脱敏配置 JSON"
          aria-label="脱敏配置 JSON"
        />
      </article>

      <article className="controlPanelCard">
        <h4>Hermes upstream</h4>
        <p>{data?.upstream.summary || "还没有 upstream 检查报告。"}</p>
        <p>这里不会自动合并或发布官方更新。</p>
        <button type="button" className="secondaryButton compactButton" onClick={() => void load()} disabled={busy}>
          刷新
        </button>
      </article>

      {message && <p className="inlineStatus">{message}</p>}
      {exportData && <TechnicalDetails title="最近脱敏导出" data={exportData} />}
      {data && <TechnicalDetails title="高级状态详情" data={data} />}
    </section>
  );
}
