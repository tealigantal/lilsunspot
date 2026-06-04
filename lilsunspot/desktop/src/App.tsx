import { useEffect, useMemo, useState } from "react";
import {
  connectDaemon,
  getAppState,
  getCurrentMode,
  getDaemonUrl,
  getHealth,
  getModes,
  getProviders,
  getRuntimeInfo,
  getSafetyApprovals,
  getSafetyPolicy,
  getWeixinCommands,
  getWeixinStatus,
  isDesktopRuntime,
  openProviderKeyUrl,
  runDoctor,
  runRepair,
  saveProvider,
  selectMode,
  sendChatMessage,
  setRuntimeToken,
  testProvider
} from "./api";
import type {
  AppBootState,
  AppState,
  CurrentMode,
  DaemonConnectStatus,
  DoctorResult,
  HealthStatus,
  ModeProfile,
  Provider,
  ProviderTestResult,
  RuntimeInfo,
  SafetyApprovals,
  SafetyPolicy,
  WeixinCommand,
  WeixinStatus
} from "./types";

type Page = "home" | "provider" | "chat" | "mode" | "weixin" | "safety" | "doctor";
type WizardStep = 1 | 2 | 3;
type ChatState = "idle" | "loading" | "success" | "error";

const PAGES: { id: Page; label: string }[] = [
  { id: "home", label: "首页" },
  { id: "provider", label: "模型" },
  { id: "chat", label: "聊天" },
  { id: "mode", label: "输出风格" },
  { id: "weixin", label: "微信" },
  { id: "safety", label: "安全" },
  { id: "doctor", label: "诊断" }
];

const RECOMMENDED_PROVIDER_IDS = ["deepseek", "kimi", "qwen", "ollama"];

const PROVIDER_COPY: Record<string, { description: string; keyRequirement: string }> = {
  deepseek: { description: "便宜易用，适合先跑通。", keyRequirement: "需要 API Key" },
  kimi: { description: "长文本能力好，有官方 API Platform。", keyRequirement: "需要 API Key" },
  qwen: { description: "国内云服务，支持 OpenAI 兼容接口。", keyRequirement: "需要 API Key" },
  ollama: { description: "模型运行在本机，适合离线尝试。", keyRequirement: "通常不用 API Key" },
  openrouter: { description: "海外聚合服务，适合已有账号用户。", keyRequirement: "需要 API Key" },
  openai: { description: "OpenAI 官方服务，适合海外网络环境。", keyRequirement: "需要 API Key" }
};

function asText(value: unknown) {
  return JSON.stringify(value, null, 2);
}

function userFacingStatus(
  state: AppBootState,
  appState: AppState | null,
  connection: DaemonConnectStatus | null
) {
  if (state === "starting_daemon") {
    return {
      title: "正在准备小黑子……",
      message: "正在启动本地服务，并检查模型设置。",
      primaryAction: "",
      secondaryAction: "",
      showTechDetails: false
    };
  }
  if (state === "daemon_failed") {
    return {
      title: "小黑子没有成功启动",
      message: connection?.message_cn || "可能原因：本地服务没有启动，或被安全软件拦截。",
      primaryAction: "一键修复",
      secondaryAction: "重新检查",
      showTechDetails: true
    };
  }
  if (state === "provider_missing") {
    return {
      title: appState?.title || "还差一步：选择一个模型服务",
      message: appState?.message || "选择后，小黑子就可以开始聊天。API Key 只保存在你的电脑本地。",
      primaryAction: "开始设置模型",
      secondaryAction: "一键检查",
      showTechDetails: true
    };
  }
  if (state === "chat_ready") {
    return {
      title: appState?.title || "小黑子已准备好",
      message: appState?.message || "可以开始聊天。",
      primaryAction: "开始聊天",
      secondaryAction: "设置模型",
      showTechDetails: true
    };
  }
  return {
    title: "正在检查小黑子状态",
    message: "小黑子本地服务已启动，正在读取模型设置。",
    primaryAction: "重新检查",
    secondaryAction: "",
    showTechDetails: true
  };
}

function providerDescription(provider: Provider) {
  return PROVIDER_COPY[provider.id] || { description: provider.notes || "OpenAI 兼容模型服务。", keyRequirement: "需要配置" };
}

export default function App() {
  const [page, setPage] = useState<Page>("home");
  const [devMode] = useState(!isDesktopRuntime());
  const [devToken, setDevToken] = useState("");
  const [connection, setConnection] = useState<DaemonConnectStatus | null>(null);
  const [healthBody, setHealthBody] = useState<HealthStatus | null>(null);
  const [appState, setAppState] = useState<AppState | null>(null);
  const [runtime, setRuntime] = useState<RuntimeInfo | null>(null);
  const [bootState, setBootState] = useState<AppBootState>("starting_daemon");
  const [providers, setProviders] = useState<Provider[]>([]);
  const [selectedProvider, setSelectedProvider] = useState("");
  const [model, setModel] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [providerTest, setProviderTest] = useState<ProviderTestResult | null>(null);
  const [wizardStep, setWizardStep] = useState<WizardStep>(1);
  const [showMoreProviders, setShowMoreProviders] = useState(false);
  const [chatInput, setChatInput] = useState("");
  const [chatReply, setChatReply] = useState("");
  const [chatError, setChatError] = useState("");
  const [chatEngine, setChatEngine] = useState("");
  const [chatState, setChatState] = useState<ChatState>("idle");
  const [modes, setModes] = useState<ModeProfile[]>([]);
  const [currentMode, setCurrentMode] = useState<CurrentMode | null>(null);
  const [weixinStatus, setWeixinStatus] = useState<WeixinStatus | null>(null);
  const [weixinCommands, setWeixinCommands] = useState<WeixinCommand[]>([]);
  const [safetyPolicy, setSafetyPolicy] = useState<SafetyPolicy | null>(null);
  const [approvals, setApprovals] = useState<SafetyApprovals | null>(null);
  const [doctor, setDoctor] = useState<DoctorResult | null>(null);
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState(false);

  const selectedProviderConfig = useMemo(
    () => providers.find((provider) => provider.id === selectedProvider) || null,
    [providers, selectedProvider]
  );
  const visibleRecommendedProviders = providers.filter((provider) => RECOMMENDED_PROVIDER_IDS.includes(provider.id));
  const moreProviders = providers.filter((provider) => !RECOMMENDED_PROVIDER_IDS.includes(provider.id));
  const homeStatus = userFacingStatus(bootState, appState, connection);
  const chatConfigured = bootState === "chat_ready";
  const chatCanSend = chatConfigured && Boolean(chatInput.trim()) && !busy;

  useEffect(() => {
    void bootstrapConnection();
  }, []);

  useEffect(() => {
    if (page === "provider" && providers.length === 0) {
      void loadProviders();
    }
  }, [page, providers.length]);

  async function withStatus(action: () => Promise<void>) {
    setBusy(true);
    setStatus("");
    try {
      await action();
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "操作失败。");
    } finally {
      setBusy(false);
    }
  }

  async function bootstrapConnection() {
    setBootState("starting_daemon");
    try {
      const connected = await connectDaemon();
      if (connected) {
        setConnection(connected);
        if (!connected.ok) {
          setBootState("daemon_failed");
          return;
        }
      }
      await refreshHomeState();
    } catch (error) {
      setConnection({
        ok: false,
        base_url: getDaemonUrl(),
        data_dir: "",
        runtime_file: "",
        launch_attempted: true,
        message_cn: error instanceof Error ? error.message : "小黑子本地服务没有成功启动。"
      });
      setBootState("daemon_failed");
    }
  }

  async function refreshHomeState() {
    try {
      const health = await getHealth();
      setHealthBody(health);
      if (!health.ok) {
        setBootState("daemon_failed");
        return;
      }
    } catch (error) {
      setConnection((current) => ({
        ok: false,
        base_url: current?.base_url || getDaemonUrl(),
        data_dir: current?.data_dir || "",
        runtime_file: current?.runtime_file || "",
        launch_attempted: current?.launch_attempted || false,
        message_cn: error instanceof Error ? error.message : "小黑子本地服务没有响应。"
      }));
      setBootState("daemon_failed");
      return;
    }

    try {
      const state = await getAppState();
      setAppState(state);
      setBootState(state.boot);
    } catch (error) {
      setAppState({
        boot: "daemon_ready",
        title: devMode ? "开发者模式：等待调试 Token" : "正在读取模型设置",
        message: devMode ? "浏览器开发模式需要填写调试 Token；正式版不会出现这一步。" : "请重新检查小黑子状态。",
        next_action: "check_again"
      });
      setBootState(devMode ? "daemon_ready" : "daemon_failed");
      if (!devMode) {
        setStatus(error instanceof Error ? error.message : "读取状态失败。");
      }
    }

    try {
      setRuntime(await getRuntimeInfo());
    } catch {
      setRuntime(null);
    }
  }

  function applyDevToken() {
    setRuntimeToken(devToken);
    setStatus(devToken.trim() ? "开发者模式 Token 已设置。" : "请先填写开发者模式调试 Token。");
    void refreshHomeState();
  }

  async function startProviderSetup(providerId?: string) {
    setPage("provider");
    await loadProviders(providerId);
    setWizardStep(providerId ? 2 : 1);
  }

  async function loadProviders(preselect?: string) {
    await withStatus(async () => {
      const list = await getProviders();
      setProviders(list);
      const nextProvider =
        list.find((provider) => provider.id === preselect) ||
        list.find((provider) => provider.id === selectedProvider) ||
        list[0];
      if (nextProvider) {
        setSelectedProvider(nextProvider.id);
        setModel(nextProvider.default_model);
      }
    });
  }

  function chooseProvider(provider: Provider) {
    setSelectedProvider(provider.id);
    setModel(provider.default_model);
    setProviderTest(null);
  }

  async function openKeyUrl() {
    if (!selectedProvider) {
      setStatus("请先选择模型服务。");
      return;
    }
    await withStatus(async () => {
      const url = await openProviderKeyUrl(selectedProvider);
      setStatus(`已打开获取 Key 的页面：${url}`);
    });
  }

  async function pasteApiKey() {
    await withStatus(async () => {
      const text = await navigator.clipboard.readText();
      setApiKey(text.trim());
      setStatus(text.trim() ? "已从剪贴板粘贴。" : "剪贴板里没有可用内容。");
    });
  }

  async function runProviderTest() {
    if (!selectedProviderConfig) {
      setStatus("请先选择模型服务。");
      return;
    }
    await withStatus(async () => {
      setBootState("provider_testing");
      const result = await testProvider(selectedProvider, model, apiKey);
      setProviderTest(result);
      if (!result.ok) {
        setBootState("provider_missing");
        setStatus(result.title);
        return;
      }
      const saved = await saveProvider(selectedProvider, result.model, apiKey);
      setStatus(`已保存 ${saved.provider} / ${saved.model}。`);
      setWizardStep(3);
      await refreshHomeState();
    });
  }

  async function sendMessage() {
    const message = chatInput.trim();
    if (!message) {
      setChatState("error");
      setChatError("请先输入消息。");
      return;
    }
    if (!chatConfigured) {
      setChatState("error");
      setChatError("请先完成模型配置。");
      return;
    }

    setBusy(true);
    setStatus("");
    setChatState("loading");
    setChatReply("");
    setChatError("");
    setChatEngine("");
    try {
      const result = await sendChatMessage(message);
      if (!result.ok) {
        setChatState("error");
        setChatError(`${result.message}\n${result.suggestion}`);
        return;
      }
      setChatState("success");
      setChatReply(result.reply);
      setChatEngine(`${result.provider} / ${result.model} / ${result.engine}`);
    } catch (error) {
      setChatState("error");
      setChatError(error instanceof Error ? error.message : "发送失败，请稍后再试。");
    } finally {
      setBusy(false);
    }
  }

  async function loadModes() {
    await withStatus(async () => {
      setModes(await getModes());
      setCurrentMode(await getCurrentMode());
    });
  }

  async function chooseMode(mode: string) {
    await withStatus(async () => {
      setCurrentMode(await selectMode(mode));
    });
  }

  async function loadWeixin() {
    await withStatus(async () => {
      setWeixinStatus(await getWeixinStatus());
      setWeixinCommands(await getWeixinCommands());
    });
  }

  async function loadSafety() {
    await withStatus(async () => {
      setSafetyPolicy(await getSafetyPolicy());
      setApprovals(await getSafetyApprovals());
    });
  }

  async function runDoctorCheck() {
    await withStatus(async () => {
      setDoctor(await runDoctor());
    });
  }

  async function runRepairPlaceholder() {
    await withStatus(async () => {
      if (bootState === "daemon_failed") {
        await bootstrapConnection();
        return;
      }
      const result = await runRepair();
      setStatus(`${result.message} ${result.suggestion}`);
    });
  }

  function exportDiagnosticsPlaceholder() {
    setStatus("导出诊断包功能正在接入。请先使用“一键检查”。");
  }

  return (
    <main className="appShell">
      <header className="appHeader">
        <div>
          <h1>Lilsunspot 小黑子</h1>
          <p>个人 AI 助手，运行在你的电脑本地</p>
        </div>
        <button type="button" className="secondaryButton" onClick={bootstrapConnection} disabled={busy}>
          重新检查
        </button>
      </header>

      <nav className="tabs" aria-label="页面导航">
        {PAGES.map((item) => (
          <button
            key={item.id}
            type="button"
            className={page === item.id ? "active" : ""}
            onClick={() => setPage(item.id)}
          >
            {item.label}
          </button>
        ))}
      </nav>

      {status && (
        <p className="status" role="status">
          {status}
        </p>
      )}

      {devMode && (
        <details className="devPanel">
          <summary>开发者模式：浏览器调试连接</summary>
          <p>这里用于浏览器开发调试，正式桌面版不会显示。</p>
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
            <button type="button" onClick={applyDevToken} disabled={busy}>
              使用调试 Token
            </button>
          </div>
        </details>
      )}

      {page === "home" && (
        <section className="homePanel" aria-labelledby="home-title">
          {bootState === "starting_daemon" ? (
            <div className="bootCard">
              <h2 id="home-title">正在准备小黑子……</h2>
              <div className="progressTrack" aria-label="准备进度">
                <span />
              </div>
              <ul className="bootList">
                <li>正在启动本地服务</li>
                <li>正在检查运行环境</li>
                <li>正在读取模型设置</li>
              </ul>
            </div>
          ) : (
            <>
              <div className={`heroStatus ${bootState === "daemon_failed" ? "errorState" : ""}`}>
                <div className="statusSteps" aria-label="当前状态">
                  {bootState === "daemon_failed" ? (
                    <p className="failed">● 小黑子未启动</p>
                  ) : (
                    <p className="done">● 小黑子已启动</p>
                  )}
                  <p className={bootState === "chat_ready" ? "done" : "pending"}>
                    ○ 模型服务{bootState === "chat_ready" ? "已设置" : "未设置"}
                  </p>
                  <p className="pending">○ 微信未连接</p>
                </div>
                <h2 id="home-title">{homeStatus.title}</h2>
                <p>{homeStatus.message}</p>
                <div className="primaryActions">
                  {bootState === "daemon_failed" ? (
                    <>
                      <button type="button" onClick={runRepairPlaceholder} disabled={busy}>
                        一键修复
                      </button>
                      <button type="button" className="secondaryButton" onClick={bootstrapConnection} disabled={busy}>
                        重新检查
                      </button>
                      <button type="button" className="secondaryButton" onClick={exportDiagnosticsPlaceholder}>
                        导出诊断包
                      </button>
                    </>
                  ) : (
                    <>
                      <button
                        type="button"
                        onClick={() => (bootState === "chat_ready" ? setPage("chat") : void startProviderSetup())}
                        disabled={busy}
                      >
                        {homeStatus.primaryAction}
                      </button>
                      <button
                        type="button"
                        className="secondaryButton"
                        onClick={() => (bootState === "chat_ready" ? startProviderSetup() : runDoctorCheck())}
                        disabled={busy}
                      >
                        {homeStatus.secondaryAction}
                      </button>
                    </>
                  )}
                </div>
              </div>

              {bootState === "provider_missing" && (
                <div className="quickStart">
                  <h3>常用入口</h3>
                  <div className="chipRow">
                    {RECOMMENDED_PROVIDER_IDS.map((id) => (
                      <button key={id} type="button" className="chipButton" onClick={() => void startProviderSetup(id)}>
                        {id === "qwen" ? "通义千问" : id === "ollama" ? "本地 Ollama" : id === "deepseek" ? "DeepSeek" : "Kimi"}
                      </button>
                    ))}
                  </div>
                  <p>
                    遇到问题？
                    <button type="button" className="linkButton" onClick={runDoctorCheck} disabled={busy}>
                      一键检查
                    </button>
                  </p>
                </div>
              )}

              <div className="stateGrid">
                <article>
                  <h3>模型服务</h3>
                  <p>{bootState === "chat_ready" ? `已设置：${runtime?.provider || "已配置"}` : "还没有设置"}</p>
                  <button type="button" className="secondaryButton" onClick={() => void startProviderSetup()} disabled={busy}>
                    {bootState === "chat_ready" ? "调整模型" : "开始设置"}
                  </button>
                </article>
                <article>
                  <h3>输出风格</h3>
                  <p>{currentMode?.current || "默认风格"}</p>
                  <button type="button" className="secondaryButton" onClick={() => setPage("mode")}>
                    设置风格
                  </button>
                </article>
                <article>
                  <h3>微信</h3>
                  <p>未连接</p>
                  <button type="button" className="secondaryButton" onClick={() => setPage("weixin")}>
                    查看微信
                  </button>
                </article>
                <article>
                  <h3>安全</h3>
                  <p>暂无待审批操作</p>
                  <button type="button" className="secondaryButton" onClick={() => setPage("safety")}>
                    查看安全
                  </button>
                </article>
              </div>

              <details className="techDetails">
                <summary>技术详情</summary>
                <pre>
                  {asText({
                    local_service_url: connection?.base_url || getDaemonUrl(),
                    launch_attempted: connection?.launch_attempted || false,
                    health: healthBody,
                    runtime
                  })}
                </pre>
              </details>
            </>
          )}
        </section>
      )}

      {page === "provider" && (
        <section className="panel providerWizard" aria-labelledby="provider-title">
          {wizardStep === 1 && (
            <>
              <div className="panelHeader">
                <div>
                  <h2 id="provider-title">设置模型服务</h2>
                  <p>选择你要使用的模型服务</p>
                </div>
                <span>第 1/3 步</span>
              </div>
              <h3>推荐给中国大陆用户</h3>
              <div className="providerGrid">
                {visibleRecommendedProviders.map((provider) => {
                  const copy = providerDescription(provider);
                  return (
                    <button
                      key={provider.id}
                      type="button"
                      className={selectedProvider === provider.id ? "providerCard selected" : "providerCard"}
                      onClick={() => chooseProvider(provider)}
                    >
                      <strong>{provider.display_name}</strong>
                      <span>{copy.description}</span>
                      <em>{copy.keyRequirement}</em>
                    </button>
                  );
                })}
              </div>
              <details open={showMoreProviders} onToggle={(event) => setShowMoreProviders(event.currentTarget.open)}>
                <summary>更多服务</summary>
                <div className="chipRow">
                  {moreProviders.map((provider) => (
                    <button
                      key={provider.id}
                      type="button"
                      className={selectedProvider === provider.id ? "chipButton activeChip" : "chipButton"}
                      onClick={() => chooseProvider(provider)}
                    >
                      {provider.display_name}
                    </button>
                  ))}
                </div>
              </details>
              <div className="primaryActions">
                <button type="button" onClick={() => setWizardStep(2)} disabled={busy || !selectedProvider}>
                  下一步
                </button>
              </div>
            </>
          )}

          {wizardStep === 2 && (
            <>
              <div className="panelHeader">
                <div>
                  <h2 id="provider-title">填写 API Key</h2>
                  <p>API Key 是模型服务给你的访问钥匙，只会保存在你的电脑本地。</p>
                </div>
                <span>第 2/3 步</span>
              </div>
              <div className="selectedProviderLine">
                当前模型服务：<strong>{selectedProviderConfig?.display_name || "未选择"}</strong>
              </div>
              <button type="button" className="secondaryButton" onClick={openKeyUrl} disabled={busy || !selectedProvider}>
                打开官网获取 Key
              </button>
              <label>
                API Key
                <input
                  value={apiKey}
                  onChange={(event) => setApiKey(event.target.value)}
                  type="password"
                  placeholder={selectedProviderConfig?.type === "local" ? "本地模型可留空" : "粘贴 API Key"}
                />
              </label>
              <div className="formRow">
                <button type="button" className="secondaryButton" onClick={pasteApiKey} disabled={busy}>
                  从剪贴板粘贴
                </button>
                <button type="button" onClick={runProviderTest} disabled={busy || !selectedProvider}>
                  测试连接
                </button>
              </div>
              <div className={providerTest?.ok === false ? "inlineError" : "inlineState"}>
                连接状态：
                {providerTest ? (providerTest.ok ? providerTest.message : providerTest.title) : "尚未测试"}
              </div>
              {providerTest?.ok === false && (
                <div className="errorBox" role="alert">
                  <h3>{providerTest.title}</h3>
                  <p>{providerTest.message}</p>
                  <div className="chipRow">
                    {providerTest.actions.map((action) => (
                      <span key={action} className="actionChip">
                        {action}
                      </span>
                    ))}
                  </div>
                  <details>
                    <summary>技术详情</summary>
                    <pre>{asText(providerTest.safe_details)}</pre>
                  </details>
                </div>
              )}
              <details className="techDetails">
                <summary>高级设置</summary>
                <p>Base URL、模型名、自定义 Header 将在后续版本开放编辑。当前使用服务商推荐值。</p>
                <pre>{asText({ base_url: selectedProviderConfig?.base_url, model })}</pre>
              </details>
              <div className="formRow">
                <button type="button" className="secondaryButton" onClick={() => setWizardStep(1)} disabled={busy}>
                  上一步
                </button>
              </div>
            </>
          )}

          {wizardStep === 3 && (
            <>
              <div className="panelHeader">
                <div>
                  <h2 id="provider-title">模型服务已连接</h2>
                  <p>已成功连接 {selectedProviderConfig?.display_name || selectedProvider}</p>
                </div>
                <span>第 3/3 步</span>
              </div>
              <p className="successText">默认模型：{model}</p>
              <p>你现在可以开始聊天。</p>
              <div className="primaryActions">
                <button type="button" onClick={() => setPage("chat")}>
                  开始聊天
                </button>
                <button type="button" className="secondaryButton" onClick={() => setPage("mode")}>
                  继续设置输出风格
                </button>
              </div>
            </>
          )}
        </section>
      )}

      {page === "chat" && (
        <section className="panel">
          <h2>聊天</h2>
          <p>{chatConfigured ? `当前模型：${runtime?.provider || "已配置"} / ${runtime?.model || "默认模型"}` : "请先设置模型服务。"}</p>
          {!chatConfigured && (
            <div className="inlineError" role="alert">
              请先到模型页保存一个可用模型。
            </div>
          )}
          <textarea
            value={chatInput}
            onChange={(event) => setChatInput(event.target.value)}
            rows={4}
            disabled={!chatConfigured || busy}
            aria-label="聊天消息"
          />
          <div className="formRow">
            <button type="button" onClick={sendMessage} disabled={!chatCanSend}>
              {chatState === "loading" ? "发送中" : "发送"}
            </button>
            <button
              type="button"
              className="secondaryButton"
              onClick={() => {
                setChatInput("");
                setChatReply("");
                setChatError("");
                setChatEngine("");
                setChatState("idle");
              }}
              disabled={busy || (!chatInput && !chatReply && !chatError)}
            >
              清空
            </button>
          </div>
          {chatState === "loading" && <div className="inlineState">正在请求模型服务……</div>}
          {chatState === "error" && (
            <div className="errorBox" role="alert">
              <h3>发送失败</h3>
              <p>{chatError}</p>
            </div>
          )}
          {chatState === "success" && (
            <div className="chatReply" aria-live="polite">
              <span>{chatEngine}</span>
              <p>{chatReply}</p>
            </div>
          )}
          {chatState === "idle" && <div className="inlineState">尚无回复。</div>}
        </section>
      )}

      {page === "mode" && (
        <section className="panel">
          <h2>输出风格</h2>
          <p>选择小黑子回答时的默认风格。</p>
          <button type="button" onClick={loadModes} disabled={busy}>
            加载输出风格
          </button>
          <div className="list">
            {modes.map((mode) => (
              <button key={mode.id} type="button" onClick={() => chooseMode(mode.id)}>
                {mode.id}: {mode.description}
              </button>
            ))}
          </div>
          <pre>{currentMode ? asText(currentMode) : "尚未选择输出风格。"}</pre>
        </section>
      )}

      {page === "weixin" && (
        <section className="panel">
          <h2>微信</h2>
          <p>微信连接能力还是占位模块，当前版本不会扫码登录或发送消息。</p>
          <button type="button" onClick={loadWeixin} disabled={busy}>
            加载微信状态
          </button>
          <pre>{weixinStatus ? asText({ weixinStatus, weixinCommands }) : "尚未加载微信状态。"}</pre>
        </section>
      )}

      {page === "safety" && (
        <section className="panel">
          <h2>安全</h2>
          <p>查看安全审批策略和待审批操作。</p>
          <button type="button" onClick={loadSafety} disabled={busy}>
            加载安全状态
          </button>
          <pre>{safetyPolicy ? asText({ safetyPolicy, approvals }) : "尚未加载安全状态。"}</pre>
        </section>
      )}

      {page === "doctor" && (
        <section className="panel">
          <h2>诊断</h2>
          <p>遇到问题时，可以先运行一键检查。</p>
          <div className="formRow">
            <button type="button" onClick={runDoctorCheck} disabled={busy}>
              一键检查
            </button>
            <button type="button" className="secondaryButton" onClick={runRepairPlaceholder} disabled={busy}>
              一键修复
            </button>
            <button type="button" className="secondaryButton" onClick={exportDiagnosticsPlaceholder}>
              导出诊断包
            </button>
          </div>
          <details className="techDetails">
            <summary>技术日志</summary>
            <pre>{doctor ? asText(doctor) : "尚未运行诊断。"}</pre>
          </details>
        </section>
      )}
    </main>
  );
}
