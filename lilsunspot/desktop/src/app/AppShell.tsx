import { useState } from "react";
import lilsunspotIcon from "../assets/lilsunspot-icon.png";
import type { CurrentMode } from "../types";
import { SettingsDrawer, type SettingsTab } from "../features/settings/SettingsDrawer";
import type { ChatMessage } from "../features/chat/ChatTranscript";
import { BootGate } from "./BootGate";
import { useBootstrapState } from "./useBootstrapState";

export function AppShell() {
  const bootstrapState = useBootstrapState();
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [settingsTab, setSettingsTab] = useState<SettingsTab>("model");
  const [forceOnboarding, setForceOnboarding] = useState(false);
  const [firstChatMessages, setFirstChatMessages] = useState<ChatMessage[]>([]);
  const [devToken, setDevToken] = useState("");
  const [_lastMode, setLastMode] = useState<CurrentMode | null>(null);

  async function refreshAndReturn() {
    setForceOnboarding(false);
    await bootstrapState.refresh();
  }

  async function handleSaved() {
    setForceOnboarding(false);
    await bootstrapState.refresh();
  }

  function handleFirstChatDone(messages: ChatMessage[]) {
    setFirstChatMessages(messages);
    setForceOnboarding(false);
    void bootstrapState.refresh();
  }

  function setupModel() {
    setSettingsOpen(false);
    setForceOnboarding(true);
  }

  function openSettings(tab: SettingsTab = "model") {
    setSettingsTab(tab);
    setSettingsOpen(true);
  }

  return (
    <main className="appShell">
      <header className="appHeader">
        <div className="brandBlock">
          <img src={lilsunspotIcon} alt="" className="brandIcon" />
          <div>
            <h1>Lilsunspot 小黑子</h1>
            <p>Windows 桌面个人 Agent，运行在你的电脑本地</p>
          </div>
        </div>
        <div className="headerActions">
          <button type="button" className="secondaryButton" onClick={bootstrapState.refresh} disabled={bootstrapState.busy}>
            重新检查
          </button>
          <button type="button" className="secondaryButton" onClick={() => openSettings("model")}>
            设置
          </button>
        </div>
      </header>

      {bootstrapState.devMode && (
        <details className="devPanel">
          <summary>开发者模式：浏览器调试连接</summary>
          <p>这里仅用于浏览器开发调试，正式桌面版不会显示，也不会要求手动填写。</p>
          <div className="formRow">
            <label>
              调试 Token
              <input
                value={devToken}
                onChange={(event) => setDevToken(event.target.value)}
                type="password"
                placeholder="仅开发模式手动填写"
              />
            </label>
            <button type="button" onClick={() => bootstrapState.applyDevToken(devToken)} disabled={!devToken.trim()}>
              使用调试 Token
            </button>
          </div>
        </details>
      )}

      <BootGate
        bootstrap={bootstrapState.bootstrap}
        forceOnboarding={forceOnboarding}
        initialMessages={firstChatMessages}
        busy={bootstrapState.busy}
        onRefresh={refreshAndReturn}
        onOpenDoctor={() => openSettings("doctor")}
        onOpenSettings={() => openSettings("model")}
        onSetupModel={setupModel}
        onBootstrapChanged={handleSaved}
        onFirstChatDone={handleFirstChatDone}
      />

      <SettingsDrawer
        open={settingsOpen}
        runtime={bootstrapState.bootstrap.runtime}
        onClose={() => setSettingsOpen(false)}
        onSetupModel={setupModel}
        onModeChanged={setLastMode}
        initialTab={settingsTab}
      />
    </main>
  );
}
