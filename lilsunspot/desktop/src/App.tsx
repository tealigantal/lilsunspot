import { useEffect, useState } from "react";
import {
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
  openProviderKeyUrl,
  readRuntimeToken,
  runDoctor,
  runRepair,
  saveProvider,
  selectMode,
  sendChatMessage,
  setRuntimeToken,
  testProvider
} from "./api";
import type {
  CurrentMode,
  DoctorResult,
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

const PAGES: { id: Page; label: string }[] = [
  { id: "home", label: "首页" },
  { id: "provider", label: "Provider" },
  { id: "chat", label: "Chat" },
  { id: "mode", label: "Mode" },
  { id: "weixin", label: "Weixin" },
  { id: "safety", label: "Safety" },
  { id: "doctor", label: "Doctor" }
];

function asText(value: unknown) {
  return JSON.stringify(value, null, 2);
}

export default function App() {
  const [page, setPage] = useState<Page>("home");
  const [token, setToken] = useState("");
  const [health, setHealth] = useState<"unknown" | "ok" | "bad">("unknown");
  const [runtime, setRuntime] = useState<RuntimeInfo | null>(null);
  const [providers, setProviders] = useState<Provider[]>([]);
  const [selectedProvider, setSelectedProvider] = useState("");
  const [model, setModel] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [providerTest, setProviderTest] = useState<ProviderTestResult | null>(null);
  const [chatInput, setChatInput] = useState("");
  const [chatReply, setChatReply] = useState("");
  const [modes, setModes] = useState<ModeProfile[]>([]);
  const [currentMode, setCurrentMode] = useState<CurrentMode | null>(null);
  const [weixinStatus, setWeixinStatus] = useState<WeixinStatus | null>(null);
  const [weixinCommands, setWeixinCommands] = useState<WeixinCommand[]>([]);
  const [safetyPolicy, setSafetyPolicy] = useState<SafetyPolicy | null>(null);
  const [approvals, setApprovals] = useState<SafetyApprovals | null>(null);
  const [doctor, setDoctor] = useState<DoctorResult | null>(null);
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    void checkHealth();
    readRuntimeToken().then((detectedToken) => {
      if (!detectedToken) {
        return;
      }
      setToken(detectedToken);
      setRuntimeToken(detectedToken);
      void refreshHome();
    });
  }, []);

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

  async function checkHealth() {
    try {
      const result = await getHealth();
      setHealth(result.ok ? "ok" : "bad");
    } catch {
      setHealth("bad");
    }
  }

  function applyToken(value = token) {
    setRuntimeToken(value);
    setStatus(value.trim() ? "Token 已设置。" : "请先填写 runtime token。");
  }

  async function refreshHome() {
    await withStatus(async () => {
      await checkHealth();
      setRuntime(await getRuntimeInfo());
    });
  }

  async function loadProviders() {
    await withStatus(async () => {
      const list = await getProviders();
      setProviders(list);
      if (list.length > 0 && !selectedProvider) {
        setSelectedProvider(list[0].id);
        setModel(list[0].default_model);
      }
    });
  }

  async function openKeyUrl() {
    if (!selectedProvider) {
      setStatus("请先选择服务商。");
      return;
    }
    await withStatus(async () => {
      const url = await openProviderKeyUrl(selectedProvider);
      window.open(url, "_blank", "noopener,noreferrer");
      setStatus("已打开 Key 页面。");
    });
  }

  async function runProviderTest() {
    await withStatus(async () => {
      setProviderTest(await testProvider(selectedProvider, model, apiKey));
    });
  }

  async function saveProviderConfig() {
    await withStatus(async () => {
      const result = await saveProvider(selectedProvider, model, apiKey);
      setStatus(`已保存 ${result.provider} / ${result.model}。`);
      setRuntime(await getRuntimeInfo());
    });
  }

  async function sendMessage() {
    await withStatus(async () => {
      const result = await sendChatMessage(chatInput);
      setChatReply(result.ok ? result.reply : `${result.message}\n${result.suggestion}`);
    });
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
      const result = await runRepair();
      setStatus(`${result.message} ${result.suggestion}`);
    });
  }

  return (
    <main className="appShell">
      <header className="header">
        <div>
          <h1>Lilsunspot 小黑子</h1>
          <p>daemon: {getDaemonUrl()}</p>
          <p>health: {health}</p>
        </div>
        <button type="button" onClick={checkHealth} disabled={busy}>
          检查 daemon
        </button>
      </header>

      <section className="tokenBar">
        <label>
          Runtime Token
          <input
            value={token}
            onChange={(event) => setToken(event.target.value)}
            onBlur={() => applyToken()}
            type="password"
            placeholder="从 runtime-token.json 粘贴"
          />
        </label>
        <button type="button" onClick={() => applyToken()} disabled={busy}>
          设置 Token
        </button>
      </section>

      <nav className="tabs" aria-label="pages">
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

      {status && <p className="status">{status}</p>}

      {page === "home" && (
        <section className="panel">
          <h2>首页</h2>
          <p>本页只显示 lilsunspotd 和本地运行目录骨架状态。</p>
          <button type="button" onClick={refreshHome} disabled={busy}>
            刷新运行状态
          </button>
          <pre>{runtime ? asText(runtime) : "尚未读取运行状态。"}</pre>
        </section>
      )}

      {page === "provider" && (
        <section className="panel">
          <h2>Provider 页</h2>
          <p>当前只保存配置并做字段检查，不调用真实 provider。</p>
          <div className="formRow">
            <button type="button" onClick={loadProviders} disabled={busy}>
              加载 Provider
            </button>
            <select
              value={selectedProvider}
              onChange={(event) => {
                const next = providers.find((provider) => provider.id === event.target.value);
                setSelectedProvider(event.target.value);
                setModel(next?.default_model || "");
              }}
            >
              <option value="">请选择</option>
              {providers.map((provider) => (
                <option key={provider.id} value={provider.id}>
                  {provider.display_name}
                </option>
              ))}
            </select>
          </div>
          <label>
            模型
            <input value={model} onChange={(event) => setModel(event.target.value)} />
          </label>
          <label>
            API Key
            <input
              value={apiKey}
              onChange={(event) => setApiKey(event.target.value)}
              type="password"
              placeholder="本地模型可留空"
            />
          </label>
          <div className="formRow">
            <button type="button" onClick={openKeyUrl} disabled={busy || !selectedProvider}>
              打开 Key 页面
            </button>
            <button type="button" onClick={runProviderTest} disabled={busy || !selectedProvider}>
              字段检查
            </button>
            <button type="button" onClick={saveProviderConfig} disabled={busy || !selectedProvider}>
              保存配置
            </button>
          </div>
          <pre>{providerTest ? asText(providerTest) : "尚未检查 Provider。"}</pre>
        </section>
      )}

      {page === "chat" && (
        <section className="panel">
          <h2>Chat 页</h2>
          <p>当前只调用 daemon 的聊天占位接口，不调用真实模型。</p>
          <textarea value={chatInput} onChange={(event) => setChatInput(event.target.value)} rows={4} />
          <button type="button" onClick={sendMessage} disabled={busy || !chatInput.trim()}>
            发送
          </button>
          <pre>{chatReply || "尚无回复。"}</pre>
        </section>
      )}

      {page === "mode" && (
        <section className="panel">
          <h2>Mode 页</h2>
          <p>输出模式配置骨架。</p>
          <button type="button" onClick={loadModes} disabled={busy}>
            加载模式
          </button>
          <div className="list">
            {modes.map((mode) => (
              <button key={mode.id} type="button" onClick={() => chooseMode(mode.id)}>
                {mode.id}: {mode.description}
              </button>
            ))}
          </div>
          <pre>{currentMode ? asText(currentMode) : "尚未选择模式。"}</pre>
        </section>
      )}

      {page === "weixin" && (
        <section className="panel">
          <h2>Weixin 页</h2>
          <p>微信 gateway 占位，不扫码、不登录、不发消息。</p>
          <button type="button" onClick={loadWeixin} disabled={busy}>
            加载 Weixin 状态
          </button>
          <pre>{weixinStatus ? asText({ weixinStatus, weixinCommands }) : "尚未加载 Weixin 状态。"}</pre>
        </section>
      )}

      {page === "safety" && (
        <section className="panel">
          <h2>Safety 页</h2>
          <p>安全审批策略和待审批队列占位。</p>
          <button type="button" onClick={loadSafety} disabled={busy}>
            加载安全策略
          </button>
          <pre>{safetyPolicy ? asText({ safetyPolicy, approvals }) : "尚未加载安全策略。"}</pre>
        </section>
      )}

      {page === "doctor" && (
        <section className="panel">
          <h2>Doctor 页</h2>
          <p>诊断和修复占位。</p>
          <div className="formRow">
            <button type="button" onClick={runDoctorCheck} disabled={busy}>
              运行诊断
            </button>
            <button type="button" onClick={runRepairPlaceholder} disabled={busy}>
              修复占位
            </button>
          </div>
          <pre>{doctor ? asText(doctor) : "尚未运行诊断。"}</pre>
        </section>
      )}
    </main>
  );
}
