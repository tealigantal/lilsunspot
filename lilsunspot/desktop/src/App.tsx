import { useState } from "react";

const DAEMON_URL = "http://127.0.0.1:8765";
const TOKEN_HINT = "需要读取 runtime-token.json 后访问受保护接口。Day1 暂未做自动读取。";

type ResultState = {
  label: string;
  ok: boolean;
  body: string;
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
  const [result, setResult] = useState<ResultState>({
    label: "未检查",
    ok: true,
    body: "点击 Health 检查按钮确认 daemon 是否启动。"
  });
  const [loading, setLoading] = useState<string | null>(null);

  async function callEndpoint(label: string, path: string, protectedApi: boolean) {
    if (protectedApi && !token.trim()) {
      setResult({ label, ok: false, body: TOKEN_HINT });
      return;
    }

    setLoading(label);
    try {
      const headers: HeadersInit = protectedApi
        ? { "X-Lilsunspot-Token": token.trim() }
        : {};
      const response = await fetch(`${DAEMON_URL}${path}`, { headers });
      const body = await parseResponse(response);
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

  return (
    <main className="appShell">
      <section className="header">
        <h1>Lilsunspot 小黑子</h1>
        <p>当前状态：Day1 开发骨架</p>
        <p>daemon 地址：{DAEMON_URL}</p>
      </section>

      <section className="controls" aria-label="daemon checks">
        <label className="tokenField">
          <span>Runtime Token</span>
          <input
            value={token}
            onChange={(event) => setToken(event.target.value)}
            placeholder="从 runtime-token.json 手动粘贴"
            type="password"
          />
        </label>
        {!token.trim() && <p className="hint">{TOKEN_HINT}</p>}

        <div className="buttonRow">
          <button onClick={() => callEndpoint("Health", "/health", false)} disabled={loading !== null}>
            {loading === "Health" ? "检查中..." : "Health 检查"}
          </button>
          <button onClick={() => callEndpoint("Providers", "/providers", true)} disabled={loading !== null}>
            {loading === "Providers" ? "检查中..." : "Providers 检查"}
          </button>
          <button onClick={() => callEndpoint("Runtime Info", "/runtime/info", true)} disabled={loading !== null}>
            {loading === "Runtime Info" ? "检查中..." : "Runtime Info 检查"}
          </button>
          <button onClick={() => callEndpoint("Doctor", "/doctor/run", true)} disabled={loading !== null}>
            {loading === "Doctor" ? "检查中..." : "Doctor 检查"}
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
