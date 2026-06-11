import { useEffect, useMemo, useState } from "react";
import {
  createMemory,
  createReminder,
  deleteMemory,
  deleteReminder,
  getCapabilities,
  getDiagnosticsSummary,
  getMemories,
  getProviderCapabilities,
  getReminders,
  updateCapability,
  updateMemory,
  updateReminder
} from "../../api";
import type { DiagnosticsSummary, ModelCapabilities, ProductCapability, ProductMemory, ProductReminder } from "../../types";
import { StatusBadge } from "../../shared/components/StatusBadge";

function yesNo(value: boolean) {
  return value ? "可用" : "未启用";
}

function modelCapabilityText(model: ModelCapabilities | null) {
  if (!model?.configured) {
    return "未设置模型";
  }
  const image = model.supports_image ? "可识别图片" : "仅预览图片";
  const files = model.supports_files ? "可读文件摘要" : "文件能力待设置";
  return `${model.provider_name} / ${model.model} · ${image} · ${files}`;
}

function processModelText(summary: DiagnosticsSummary | null) {
  const process = summary?.local_service.runtime_process;
  if (!process?.pid) {
    return "服务进程信息待刷新。";
  }
  const packaged = process.packaged ? "安装版" : "开发环境";
  const parent = process.parent_pid ? `，父进程 ${process.parent_pid}` : "";
  return `${packaged}服务 pid ${process.pid}${parent}`;
}

export function ControlCenterSettings() {
  const [summary, setSummary] = useState<DiagnosticsSummary | null>(null);
  const [model, setModel] = useState<ModelCapabilities | null>(null);
  const [reminders, setReminders] = useState<ProductReminder[]>([]);
  const [memories, setMemories] = useState<ProductMemory[]>([]);
  const [capabilities, setCapabilities] = useState<ProductCapability[]>([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [reminderTitle, setReminderTitle] = useState("");
  const [reminderPrompt, setReminderPrompt] = useState("");
  const [reminderDueAt, setReminderDueAt] = useState("");
  const [memoryText, setMemoryText] = useState("");

  const enabledCapabilities = useMemo(
    () => capabilities.filter((capability) => capability.enabled).length,
    [capabilities]
  );

  async function load() {
    setBusy(true);
    setMessage("");
    try {
      const [nextSummary, nextModel, nextReminders, nextMemories, nextCapabilities] = await Promise.all([
        getDiagnosticsSummary(),
        getProviderCapabilities(),
        getReminders(),
        getMemories(),
        getCapabilities()
      ]);
      setSummary(nextSummary);
      setModel(nextModel);
      setReminders(nextReminders);
      setMemories(nextMemories);
      setCapabilities(nextCapabilities);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "控制台读取失败。");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function addReminder() {
    if (!reminderTitle.trim() || !reminderPrompt.trim()) {
      setMessage("提醒标题和内容都要填写。");
      return;
    }
    setBusy(true);
    try {
      const reminder = await createReminder(reminderTitle, reminderPrompt, reminderDueAt);
      setReminders((current) => [reminder, ...current]);
      setReminderTitle("");
      setReminderPrompt("");
      setReminderDueAt("");
      setMessage("提醒已保存。");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "提醒保存失败。");
    } finally {
      setBusy(false);
    }
  }

  async function completeReminder(reminder: ProductReminder) {
    const updated = await updateReminder(reminder.id, { completed: !reminder.completed_at });
    setReminders((current) => current.map((item) => (item.id === updated.id ? updated : item)));
  }

  async function removeReminder(reminder: ProductReminder) {
    await deleteReminder(reminder.id);
    setReminders((current) => current.filter((item) => item.id !== reminder.id));
  }

  async function addMemory() {
    if (!memoryText.trim()) {
      setMessage("记忆内容不能为空。");
      return;
    }
    setBusy(true);
    try {
      const memory = await createMemory(memoryText);
      setMemories((current) => [memory, ...current]);
      setMemoryText("");
      setMessage("记忆已保存。");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "记忆保存失败。");
    } finally {
      setBusy(false);
    }
  }

  async function toggleMemory(memory: ProductMemory) {
    const updated = await updateMemory(memory.id, !memory.enabled);
    setMemories((current) => current.map((item) => (item.id === updated.id ? updated : item)));
  }

  async function removeMemory(memory: ProductMemory) {
    await deleteMemory(memory.id);
    setMemories((current) => current.filter((item) => item.id !== memory.id));
  }

  async function toggleCapability(capability: ProductCapability) {
    const updated = await updateCapability(capability.id, !capability.enabled);
    setCapabilities((current) => current.map((item) => (item.id === updated.id ? updated : item)));
  }

  return (
    <section className="settingsSection controlCenter" aria-busy={busy}>
      <div className="settingsHeader">
        <div>
          <h3>控制台</h3>
          <p>诊断、搜索、提醒、记忆和能力开关集中在这里。</p>
        </div>
        <StatusBadge tone={summary?.ok ? "ok" : "warning"}>{summary?.ok ? "正常" : "需检查"}</StatusBadge>
      </div>

      <div className="controlMetricGrid">
        <article>
          <span>模型</span>
          <strong>{modelCapabilityText(model)}</strong>
        </article>
        <article>
          <span>微信</span>
          <strong>{summary?.weixin.connected ? "已连接" : summary?.weixin.status || "未连接"}</strong>
        </article>
        <article>
          <span>提醒</span>
          <strong>{summary?.counts.active_reminders ?? reminders.filter((item) => item.enabled && !item.completed_at).length}</strong>
        </article>
        <article>
          <span>能力</span>
          <strong>{enabledCapabilities}/{capabilities.length}</strong>
        </article>
      </div>

      <div className="controlPanelGrid">
        <article className="controlPanelCard">
          <h4>诊断摘要</h4>
          <p>{summary?.local_service.doctor_ok ? "本地服务检查通过。" : "有检查项需要处理。"}</p>
          <p>{processModelText(summary)}</p>
          {summary?.local_service.process_note && <p>{summary.local_service.process_note}</p>}
          <p>{summary?.upstream.summary || "还没有 upstream 报告。"}</p>
          <button type="button" className="secondaryButton compactButton" onClick={() => void load()} disabled={busy}>
            刷新
          </button>
        </article>

        <article className="controlPanelCard">
          <h4>模型能力</h4>
          <ul className="compactStatusList">
            <li>图片：{yesNo(Boolean(model?.supports_image))}</li>
            <li>文件：{yesNo(Boolean(model?.supports_files))}</li>
            <li>微信：{yesNo(Boolean(model?.supports_weixin))}</li>
          </ul>
          {(model?.limitations || []).map((item) => (
            <p key={item}>{item}</p>
          ))}
        </article>
      </div>

      <article className="controlPanelCard">
        <h4>提醒</h4>
        <div className="controlFormGrid">
          <input value={reminderTitle} onChange={(event) => setReminderTitle(event.target.value)} placeholder="标题" />
          <input value={reminderDueAt} onChange={(event) => setReminderDueAt(event.target.value)} placeholder="时间，例如 明天 09:00" />
          <textarea value={reminderPrompt} onChange={(event) => setReminderPrompt(event.target.value)} placeholder="要提醒或执行的内容" />
          <button type="button" onClick={() => void addReminder()} disabled={busy}>
            保存提醒
          </button>
        </div>
        <div className="productList">
          {reminders.map((reminder) => (
            <div key={reminder.id}>
              <strong>{reminder.title}</strong>
              <span>{reminder.due_at || "未设置时间"} · {reminder.completed_at ? "已完成" : reminder.enabled ? "启用" : "暂停"}</span>
              <p>{reminder.prompt}</p>
              <div>
                <button type="button" className="secondaryButton compactButton" onClick={() => void completeReminder(reminder)}>
                  {reminder.completed_at ? "恢复" : "完成"}
                </button>
                <button type="button" className="secondaryButton compactButton" onClick={() => void removeReminder(reminder)}>
                  删除
                </button>
              </div>
            </div>
          ))}
          {reminders.length === 0 && <p>还没有提醒。</p>}
        </div>
      </article>

      <article className="controlPanelCard">
        <h4>记忆</h4>
        <div className="controlFormGrid single">
          <textarea value={memoryText} onChange={(event) => setMemoryText(event.target.value)} placeholder="想让小黑子记住的偏好或事实" />
          <button type="button" onClick={() => void addMemory()} disabled={busy}>
            保存记忆
          </button>
        </div>
        <div className="productList">
          {memories.map((memory) => (
            <div key={memory.id}>
              <strong>{memory.enabled ? "启用" : "暂停"}</strong>
              <p>{memory.text}</p>
              <div>
                <button type="button" className="secondaryButton compactButton" onClick={() => void toggleMemory(memory)}>
                  {memory.enabled ? "暂停" : "启用"}
                </button>
                <button type="button" className="secondaryButton compactButton" onClick={() => void removeMemory(memory)}>
                  删除
                </button>
              </div>
            </div>
          ))}
          {memories.length === 0 && <p>还没有记忆。</p>}
        </div>
      </article>

      <article className="controlPanelCard">
        <h4>能力开关</h4>
        <div className="capabilitySwitchGrid">
          {capabilities.map((capability) => (
            <label key={capability.id} className="capabilitySwitch">
              <input type="checkbox" checked={capability.enabled} onChange={() => void toggleCapability(capability)} />
              <span>
                <strong>{capability.label}</strong>
                <em>{capability.requires_approval ? "需要确认" : "直接可用"}</em>
                <small>{capability.description}</small>
              </span>
            </label>
          ))}
        </div>
      </article>

      {message && (
        <p className="inlineStatus" aria-live="polite">
          {message}
        </p>
      )}
    </section>
  );
}
