import { useEffect, useState } from "react";
import lilsunspotIcon from "../assets/lilsunspot-icon.png";
import { checkUpdate, dismissUpdate, downloadAndInstallUpdate, isDesktopRuntime } from "../api";
import { SettingsDrawer, type SettingsTab } from "../features/settings/SettingsDrawer";
import type { ChatMessage } from "../features/chat/ChatTranscript";
import { modeName } from "../features/mode/ModeQuickPanel";
import { useModeState } from "../features/mode/ModeState";
import { displayProvider } from "../features/model/ProviderCard";
import { WeixinSettings } from "../features/settings/WeixinSettings";
import { HistoryPage } from "../features/history/HistoryPage";
import { TasksPage } from "../features/tasks/TasksPage";
import type { AppUpdateStatus } from "../types";
import { BootGate } from "./BootGate";
import { useBootstrapState } from "./useBootstrapState";
import { useModelServiceState } from "./useModelServiceState";

type ConsoleView = "chat" | "weixin" | "tasks" | "history";

const NAV_ITEMS: { id: ConsoleView; short: string; label: string }[] = [
  { id: "chat", short: "CH", label: "聊天" },
  { id: "weixin", short: "WX", label: "微信" },
  { id: "tasks", short: "TK", label: "任务" },
  { id: "history", short: "HS", label: "历史" }
];

const VIEW_COPY: Record<ConsoleView, { title: string; subtitle: string }> = {
  chat: { title: "和小黑子聊天", subtitle: "桌面聊天、任务整理和本地能力状态" },
  weixin: { title: "微信连接", subtitle: "私聊同步、文件接收和自然语言调整风格" },
  tasks: { title: "任务", subtitle: "提醒、定时总结和定时检查" },
  history: { title: "历史", subtitle: "搜索、恢复和管理桌面/微信对话" }
};

export function AppShell() {
  const bootstrapState = useBootstrapState();
  const modeState = useModeState();
  const runtime = bootstrapState.bootstrap.runtime;
  const modelService = useModelServiceState({
    configured: runtime.configured,
    provider: runtime.provider,
    model: runtime.model
  });
  const [activeView, setActiveView] = useState<ConsoleView>("chat");
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [settingsTab, setSettingsTab] = useState<SettingsTab>("model");
  const [forceOnboarding, setForceOnboarding] = useState(false);
  const [firstChatMessages, setFirstChatMessages] = useState<ChatMessage[]>([]);
  const [requestedConversationId, setRequestedConversationId] = useState("");
  const [devToken, setDevToken] = useState("");
  const [updateStatus, setUpdateStatus] = useState<AppUpdateStatus | null>(null);
  const [updateNoticeHidden, setUpdateNoticeHidden] = useState(false);
  const [updateNoticeMessage, setUpdateNoticeMessage] = useState("");

  async function refreshAndReturn() {
    setForceOnboarding(false);
    await bootstrapState.refresh();
    await modelService.refreshCapabilities();
  }

  async function handleSaved() {
    setForceOnboarding(false);
    await bootstrapState.refresh();
    await modelService.refreshCapabilities();
  }

  async function handleLocalProviderReset() {
    setSettingsOpen(false);
    setActiveView("chat");
    setFirstChatMessages([]);
    modelService.clearModelCapabilities();
    await bootstrapState.refresh();
    setForceOnboarding(true);
  }

  function handleFirstChatDone(messages: ChatMessage[]) {
    setFirstChatMessages(messages);
    setForceOnboarding(false);
    void bootstrapState.refresh();
  }

  function setupModel() {
    if (bootstrapState.bootstrap.runtime.configured) {
      setSettingsTab("model");
      setSettingsOpen(true);
      setForceOnboarding(false);
      return;
    }
    setSettingsOpen(false);
    setForceOnboarding(true);
    setActiveView("chat");
  }

  function openSettings(tab: SettingsTab = "model") {
    setSettingsTab(tab);
    setSettingsOpen(true);
  }

  function openConversation(conversationId: string) {
    setRequestedConversationId(conversationId);
    setActiveView("chat");
  }

  useEffect(() => {
    if (!isDesktopRuntime()) {
      return;
    }
    let cancelled = false;
    void checkUpdate().then((status) => {
      if (!cancelled) {
        setUpdateStatus(status);
      }
    });
    return () => {
      cancelled = true;
    };
  }, []);

  async function installUpdateFromNotice() {
    setUpdateNoticeMessage("正在下载并安装更新。");
    try {
      const result = await downloadAndInstallUpdate();
      setUpdateNoticeMessage(result.message);
    } catch (error) {
      setUpdateNoticeMessage(error instanceof Error ? error.message : "更新下载或安装失败。");
    }
  }

  async function dismissUpdateFromNotice() {
    const update = updateStatus?.update;
    if (!update) {
      return;
    }
    try {
      await dismissUpdate(update.version);
      setUpdateStatus({
        state: "dismissed",
        update,
        message: "已忽略这个版本。"
      });
      setUpdateNoticeHidden(true);
    } catch (error) {
      setUpdateNoticeMessage(error instanceof Error ? error.message : "忽略版本失败。");
    }
  }

  function renderActiveView() {
    if (activeView === "weixin") {
      return <WeixinSettings />;
    }
    if (activeView === "tasks") {
      return <TasksPage />;
    }
    if (activeView === "history") {
      return <HistoryPage onOpenConversation={openConversation} />;
    }
    return (
      <BootGate
        bootstrap={bootstrapState.bootstrap}
        forceOnboarding={forceOnboarding}
        initialMessages={firstChatMessages}
        busy={bootstrapState.busy}
        modelCapabilities={modelService.modelCapabilities}
        providers={modelService.providers}
        providersBusy={modelService.providerState === "running"}
        providersNotice={modelService.providerNotice}
        onProvidersRefresh={modelService.refreshProviders}
        onModelCapabilitiesChanged={modelService.setModelCapabilities}
        onRefresh={refreshAndReturn}
        onOpenSettings={openSettings}
        onSetupModel={setupModel}
        onBootstrapChanged={handleSaved}
        onFirstChatDone={handleFirstChatDone}
        requestedConversationId={requestedConversationId}
        onRequestedConversationHandled={() => setRequestedConversationId("")}
      />
    );
  }

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
            {updateStatus?.state === "available" && (
              <button type="button" className="secondaryButton compactButton" onClick={() => openSettings("update")}>
                有新版本
              </button>
            )}
            <button type="button" className="secondaryButton compactButton" onClick={() => openSettings("model")}>
              设置
            </button>
          </div>
        </header>

        <div className="consoleContent">
          {updateStatus?.state === "available" && updateStatus.update && !updateNoticeHidden && (
            <article className="updatePromptCard">
              <div>
                <strong>{updateStatus.update.critical ? "重要更新可用" : "发现新版小黑子"}</strong>
                <span>
                  {updateStatus.update.version}
                  {updateStatus.update.published_at ? ` · ${updateStatus.update.published_at}` : ""}
                </span>
                {updateStatus.update.notes && <p>{updateStatus.update.notes}</p>}
                {updateNoticeMessage && <p>{updateNoticeMessage}</p>}
              </div>
              <div className="actionRow">
                <button type="button" onClick={() => void installUpdateFromNotice()}>
                  下载并安装
                </button>
                <button type="button" className="secondaryButton" onClick={() => setUpdateNoticeHidden(true)}>
                  稍后提醒
                </button>
                <button type="button" className="secondaryButton" onClick={() => void dismissUpdateFromNotice()}>
                  忽略此版本
                </button>
              </div>
            </article>
          )}
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
        providers={modelService.providers}
        providerState={modelService.providerState}
        providerNotice={modelService.providerNotice}
        onProvidersRefresh={modelService.refreshProviders}
        modelCapabilities={modelService.modelCapabilities}
        capabilityState={modelService.capabilityState}
        capabilityNotice={modelService.capabilityNotice}
        onModelCapabilitiesChanged={modelService.setModelCapabilities}
        onModelCapabilitiesRefresh={modelService.refreshCapabilities}
        onClose={() => setSettingsOpen(false)}
        onSetupModel={setupModel}
        onModelSaved={handleSaved}
        onLocalProviderReset={handleLocalProviderReset}
        updateStatus={updateStatus}
        onUpdateStatusChanged={setUpdateStatus}
        initialTab={settingsTab}
      />
    </main>
  );
}
