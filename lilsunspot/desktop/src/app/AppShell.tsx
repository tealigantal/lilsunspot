import { useState } from "react";
import lilsunspotIcon from "../assets/lilsunspot-icon.png";
import { SettingsDrawer, type SettingsTab } from "../features/settings/SettingsDrawer";
import type { ChatMessage } from "../features/chat/ChatTranscript";
import { modeName } from "../features/mode/ModeQuickPanel";
import { useModeState } from "../features/mode/ModeState";
import { displayProvider } from "../features/model/ProviderCard";
import { WeixinSettings } from "../features/settings/WeixinSettings";
import { BootGate } from "./BootGate";
import { useBootstrapState } from "./useBootstrapState";

type ConsoleView = "chat" | "weixin";

const NAV_ITEMS: { id: ConsoleView; short: string; label: string }[] = [
  { id: "chat", short: "CH", label: "聊天" },
  { id: "weixin", short: "WX", label: "微信" }
];

const VIEW_COPY: Record<ConsoleView, { title: string; subtitle: string }> = {
  chat: { title: "和小黑子聊天", subtitle: "桌面聊天、任务整理和本地 Agent 控制台" },
  weixin: { title: "微信连接", subtitle: "私聊同步、文件接收和自然语言调整风格" }
};

export function AppShell() {
  const bootstrapState = useBootstrapState();
  const modeState = useModeState();
  const [activeView, setActiveView] = useState<ConsoleView>("chat");
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [settingsTab, setSettingsTab] = useState<SettingsTab>("model");
  const [forceOnboarding, setForceOnboarding] = useState(false);
  const [firstChatMessages, setFirstChatMessages] = useState<ChatMessage[]>([]);
  const [devToken, setDevToken] = useState("");

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
    setActiveView("chat");
  }

  function openSettings(tab: SettingsTab = "model") {
    setSettingsTab(tab);
    setSettingsOpen(true);
  }

  function renderActiveView() {
    if (activeView === "weixin") {
      return <WeixinSettings />;
    }
    return (
      <BootGate
        bootstrap={bootstrapState.bootstrap}
        forceOnboarding={forceOnboarding}
        initialMessages={firstChatMessages}
        busy={bootstrapState.busy}
        onRefresh={refreshAndReturn}
        onOpenSettings={openSettings}
        onSetupModel={setupModel}
        onBootstrapChanged={handleSaved}
        onFirstChatDone={handleFirstChatDone}
      />
    );
  }

  const runtime = bootstrapState.bootstrap.runtime;
  const chatConfigured = bootstrapState.bootstrap.stage === "chat_ready" && runtime.configured;
  const connectionLabel = chatConfigured ? "已连接" : runtime.configured ? "已配置" : "未配置";
  const showDevPanel = bootstrapState.devMode && bootstrapState.bootstrap.stage === "daemon_failed";
  const activeCopy =
    activeView === "chat" && !chatConfigured
      ? { title: bootstrapState.bootstrap.stage === "starting" ? "正在准备小黑子" : "首启向导", subtitle: bootstrapState.bootstrap.message }
      : VIEW_COPY[activeView];

  return (
    <main className="appShell">
      <aside className="sideNav" aria-label="主导航">
        <img src={lilsunspotIcon} alt="小黑子" className="sideNavIcon" />
        <nav>
          {NAV_ITEMS.map((item) => (
            <button
              key={item.id}
              type="button"
              className={activeView === item.id ? "sideNavItem active" : "sideNavItem"}
              onClick={() => setActiveView(item.id)}
              aria-current={activeView === item.id ? "page" : undefined}
            >
              <strong>{item.short}</strong>
              <span>{item.label}</span>
            </button>
          ))}
        </nav>
        <div className="localStatus" aria-label="本地服务">
          <span />
          <small>LOCAL</small>
        </div>
      </aside>

      <section className="consoleFrame">
        <header className="topStatusBar">
          <div className="topTitleBlock">
            <h1>{activeCopy.title}</h1>
            <p>
              {activeView === "chat" && runtime.configured
                ? `${displayProvider(runtime.provider)} / ${runtime.model || "未选择模型"} · 本地运行`
                : activeCopy.subtitle}
            </p>
          </div>
          <div className="topBarActions">
            <span className="statusPill aqua">输出：{modeName(modeState.current?.current || "balanced")}</span>
            <span className={chatConfigured ? "statusPill green" : "statusPill warning"}>{connectionLabel}</span>
            <button type="button" className="secondaryButton compactButton" onClick={() => openSettings("model")}>
              设置
            </button>
          </div>
        </header>

        <div className="consoleContent">
          {showDevPanel && (
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
          {renderActiveView()}
        </div>
      </section>

      <SettingsDrawer
        open={settingsOpen}
        runtime={bootstrapState.bootstrap.runtime}
        onClose={() => setSettingsOpen(false)}
        onSetupModel={setupModel}
        initialTab={settingsTab}
      />
    </main>
  );
}
