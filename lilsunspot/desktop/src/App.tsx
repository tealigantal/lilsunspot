import { useState } from "react";

const DAEMON_URL = "http://127.0.0.1:8765";
const TOKEN_HINT =
  "读取 %LOCALAPPDATA%/Lilsunspot/data/runtime-token.json，把 token 粘贴到这里后再调用受保护接口。";

type ResultState = {
  label: string;
  ok: boolean;
  body: string;
};

type ProviderInfo = {
  id: string;
  display_name: string;
  default_model: string;
};

function formatBody(value: unknown): string {
  return JSON.stringify(value, null, 2);
}

async function parseResponse(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) {
    return null;
  }
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

export default function App() {
  const [token, setToken] = useState("");
  const [provider, setProvider] = useState("deepseek");
  const [model, setModel] = useState("deepseek-chat");
  const [apiKey, setApiKey] = useState("");
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [result, setResult] = useState<ResultState>({
    label: "未检查",
    ok: true,
    body: "先启动 lilsunspotd，然后点击 Health 检查 daemon 是否可用。"
  });
  const [loading, setLoading] = useState<string | null>(null);

  async function callEndpoint(
    label: string,
    path: string,
    protectedApi: boolean,
    options: RequestInit = {}
  ) {
    if (protectedApi && !token.trim()) {
      setResult({ label, ok: false, body: TOKEN_HINT });
      return;
    }

    setLoading(label);
    try {
      const headers = new Headers(options.headers);
      if (protectedApi) {
        headers.set("X-Lilsunspot-Token", token.trim());
      }
      const response = await fetch(`${DAEMON_URL}${path}`, { ...options, headers });
      const body = await parseResponse(response);
      if (
        response.ok &&
        path === "/providers" &&
        typeof body === "object" &&
        body !== null &&
        Array.isArray((body as { providers?: unknown }).providers)
      ) {
        const nextProviders = (body as { providers: ProviderInfo[] }).providers;
        setProviders(nextProviders);
        const selected = nextProviders.find((item) => item.id === provider) ?? nextProviders[0];
        if (selected) {
          setProvider(selected.id);
          setModel(selected.default_model);
        }
      }
      setResult({
        label,
        ok: response.ok,
        body: formatBody(body)
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setResult({
        label,
        ok: false,
        body: `无法连接 lilsunspotd：${message}`
      });
    } finally {
      setLoading(null);
    }
  }

  function saveProvider() {
    callEndpoint("Save Provider", "/providers/save", true, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        provider,
        model,
        api_key: apiKey
      })
    });
  }

  return (
    <main className="appShell">
      <section className="header">
        <div>
          <h1>Lilsunspot 小黑子</h1>
          <p>Day2：Provider 配置骨架</p>
        </div>
        <p className="daemonUrl">daemon：{DAEMON_URL}</p>
      </section>

      <section className="controls" aria-label="daemon checks">
        <label className="field">
          <span>Runtime Token</span>
          <input
            value={token}
            onChange={(event) => setToken(event.target.value)}
            placeholder="从 runtime-token.json 粘贴"
            type="password"
            autoComplete="off"
          />
        </label>
        {!token.trim() && <p className="hint">{TOKEN_HINT}</p>}

        <div className="buttonRow">
          <button onClick={() => callEndpoint("Health", "/health", false)} disabled={loading !== null}>
            {loading === "Health" ? "检查中..." : "Health"}
          </button>
          <button onClick={() => callEndpoint("Providers", "/providers", true)} disabled={loading !== null}>
            {loading === "Providers" ? "读取中..." : "Providers"}
          </button>
          <button onClick={() => callEndpoint("Runtime Info", "/runtime/info", true)} disabled={loading !== null}>
            {loading === "Runtime Info" ? "读取中..." : "Runtime Info"}
          </button>
          <button onClick={() => callEndpoint("Doctor", "/doctor/run", true)} disabled={loading !== null}>
            {loading === "Doctor" ? "检查中..." : "Doctor"}
          </button>
        </div>
      </section>

      <section className="providerPanel" aria-label="provider save">
        <div className="fieldGrid">
          <label className="field">
            <span>Provider</span>
            <select
              value={provider}
              onChange={(event) => {
                const selected = providers.find((item) => item.id === event.target.value);
                setProvider(event.target.value);
                if (selected) {
                  setModel(selected.default_model);
                }
              }}
            >
              {(providers.length
                ? providers
                : [{ id: "deepseek", display_name: "DeepSeek", default_model: "deepseek-chat" }]
              ).map((item) => (
                <option key={item.id} value={item.id}>
                  {item.display_name}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Model</span>
            <input value={model} onChange={(event) => setModel(event.target.value)} />
          </label>
          <label className="field apiKey">
            <span>API Key</span>
            <input
              value={apiKey}
              onChange={(event) => setApiKey(event.target.value)}
              placeholder="仅发送给 lilsunspotd，不打印到控制台"
              type="password"
              autoComplete="off"
            />
          </label>
        </div>
        <div className="buttonRow">
          <button onClick={saveProvider} disabled={loading !== null || !apiKey.trim()}>
            {loading === "Save Provider" ? "保存中..." : "Save Provider"}
          </button>
        </div>
      </section>

      <section className={`result ${result.ok ? "ok" : "error"}`}>
        <h2>{result.label}</h2>
        <pre>{result.body}</pre>
      </section>
    </main>
  );
}
