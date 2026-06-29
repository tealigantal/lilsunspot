import { useEffect, useState } from "react";
import { createMemory, createProfile, deleteMemory, deleteProfile, getMemories, getProfiles, updateMemory } from "../../api";
import type { ProductMemory, ProductProfile } from "../../types";
import { StatusBadge } from "../../shared/components/StatusBadge";
import { ModeQuickPanel } from "../mode/ModeQuickPanel";

export function MemoryProfileSettings() {
  const [memories, setMemories] = useState<ProductMemory[]>([]);
  const [profiles, setProfiles] = useState<ProductProfile[]>([]);
  const [memoryText, setMemoryText] = useState("");
  const [profileName, setProfileName] = useState("");
  const [profileInstructions, setProfileInstructions] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  async function load() {
    setMessage("");
    try {
      const [nextMemories, nextProfiles] = await Promise.all([getMemories(), getProfiles()]);
      setMemories(nextMemories);
      setProfiles(nextProfiles);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "记忆和风格读取失败。");
    }
  }

  useEffect(() => {
    void load();
  }, []);

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
      setMessage("本地记忆已保存。");
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
    setMessage("已删除这条本地记录；对话历史和微信上下文不会被一起删除。");
  }

  async function addProfile() {
    if (!profileName.trim() || !profileInstructions.trim()) {
      setMessage("风格名称和说明都要填写。");
      return;
    }
    setBusy(true);
    try {
      const profile = await createProfile(profileName, profileInstructions);
      setProfiles((current) => [profile, ...current]);
      setProfileName("");
      setProfileInstructions("");
      setMessage("风格档案已保存为本地记录，暂不自动注入回复。");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "风格档案保存失败。");
    } finally {
      setBusy(false);
    }
  }

  async function removeProfile(profile: ProductProfile) {
    await deleteProfile(profile.id);
    setProfiles((current) => current.filter((item) => item.id !== profile.id));
  }

  return (
    <section className="settingsSection memoryProfileSettings">
      <div className="settingsHeader">
        <div>
          <h3>记忆与风格</h3>
          <p>当前输出模式、长期本地记忆和身份风格分开管理。</p>
        </div>
        <StatusBadge tone={memories.some((item) => item.enabled) ? "ok" : "neutral"}>
          {memories.filter((item) => item.enabled).length} 条启用
        </StatusBadge>
      </div>

      <article className="controlPanelCard">
        <h4>当前回复风格</h4>
        <ModeQuickPanel />
      </article>

      <article className="controlPanelCard">
        <h4>长期本地记忆</h4>
        <p>这里是小黑子产品层记录，不等同于清空 Hermes agent memory、聊天历史或微信路由上下文。</p>
        <div className="controlFormGrid single">
          <textarea value={memoryText} onChange={(event) => setMemoryText(event.target.value)} placeholder="例如：我喜欢先给结论，再给步骤" />
          <button type="button" onClick={() => void addMemory()} disabled={busy}>
            保存记忆
          </button>
        </div>
        <div className="productList">
          {memories.map((memory) => (
            <div key={memory.id}>
              <strong>{memory.enabled ? "启用" : "暂停"} · {memory.scope_label || "本地记录"}</strong>
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
          {memories.length === 0 && <p>还没有长期本地记忆。</p>}
        </div>
      </article>

      <article className="controlPanelCard">
        <h4>身份 / Profile</h4>
        <p>这里先保存普通用户可读的风格档案，不开放 Hermes 官方 raw Profile 编辑器。</p>
        <div className="controlFormGrid">
          <input value={profileName} onChange={(event) => setProfileName(event.target.value)} placeholder="名称，例如 工作助理" />
          <textarea value={profileInstructions} onChange={(event) => setProfileInstructions(event.target.value)} placeholder="风格或边界说明" />
          <button type="button" onClick={() => void addProfile()} disabled={busy}>
            保存档案
          </button>
        </div>
        <div className="productList">
          {profiles.map((profile) => (
            <div key={profile.id}>
              <strong>{profile.name}</strong>
              <p>{profile.instructions}</p>
              <div>
                <button type="button" className="secondaryButton compactButton" onClick={() => void removeProfile(profile)}>
                  删除
                </button>
              </div>
            </div>
          ))}
          {profiles.length === 0 && <p>还没有风格档案。</p>}
        </div>
      </article>
      {message && <p className="inlineStatus">{message}</p>}
    </section>
  );
}
