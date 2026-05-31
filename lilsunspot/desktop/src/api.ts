import type {
  AppState,
  ChatSendResult,
  CurrentMode,
  DaemonConnectStatus,
  DaemonDiscovery,
  DaemonHttpResponse,
  DoctorResult,
  HealthStatus,
  ModeProfile,
  Provider,
  ProviderTestResult,
  RepairResult,
  RuntimeInfo,
  SafetyApprovals,
  SafetyPolicy,
  SaveProviderResult,
  WeixinCommand,
  WeixinStatus
} from "./types";

const DEFAULT_DAEMON_URL = "http://127.0.0.1:8765";
const TOKEN_HEADER = "X-Lilsunspot-Token";

let runtimeToken = "";
let daemonUrl = DEFAULT_DAEMON_URL;

type ApiErrorBody = {
  detail?: string;
  message?: string;
  suggestion?: string;
  title?: string;
};

function isTauriRuntime() {
  return (
    typeof window !== "undefined" &&
    "__TAURI_INTERNALS__" in (window as Window & { __TAURI_INTERNALS__?: unknown })
  );
}

async function invokeTauri<T>(command: string, args?: Record<string, unknown>): Promise<T> {
  const tauriCore = await import("@tauri-apps/api/core");
  return tauriCore.invoke<T>(command, args);
}

export function isDesktopRuntime() {
  return isTauriRuntime();
}

export function setRuntimeToken(token: string) {
  runtimeToken = token.trim();
}

export function setDaemonConnection(discovery: Pick<DaemonDiscovery, "base_url">) {
  daemonUrl = discovery.base_url.replace(/\/+$/, "");
}

export function getDaemonUrl() {
  return daemonUrl;
}

export async function connectDaemon(): Promise<DaemonConnectStatus | null> {
  if (!isTauriRuntime()) {
    return null;
  }
  const status = await invokeTauri<DaemonConnectStatus>("connect_daemon");
  if (status.base_url) {
    daemonUrl = status.base_url.replace(/\/+$/, "");
  }
  return status;
}

export async function discoverDaemon(): Promise<DaemonDiscovery | null> {
  if (!isTauriRuntime()) {
    return null;
  }
  try {
    const discovery = await invokeTauri<DaemonDiscovery>("discover_daemon");
    if (!discovery.base_url.startsWith("http://127.0.0.1:")) {
      throw new Error("本地服务地址必须是 127.0.0.1。");
    }
    setDaemonConnection(discovery);
    return discovery;
  } catch {
    return null;
  }
}

function humanizeError(error: unknown): string {
  if (error instanceof Error) {
    if (error.message === "Failed to fetch") {
      return "小黑子本地服务没有响应。请点击“重新检查”。";
    }
    return error.message;
  }
  return "请求失败，请稍后再试。";
}

function parseBodyText(text: string): unknown {
  if (!text) {
    return null;
  }
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

async function parseBody(response: Response): Promise<unknown> {
  return parseBodyText(await response.text());
}

function errorMessageFromBody(body: unknown): string {
  if (typeof body === "string" && body.trim()) {
    return body;
  }
  if (body && typeof body === "object") {
    const value = body as ApiErrorBody;
    return value.title || value.detail || value.message || value.suggestion || "请求失败。";
  }
  return "请求失败。";
}

async function requestViaTauri<T>(path: string, options: RequestInit): Promise<T> {
  const method = (options.method || "GET").toUpperCase();
  const rawBody = typeof options.body === "string" ? options.body : undefined;
  const response = await invokeTauri<DaemonHttpResponse>("daemon_request", {
    path,
    method,
    body: rawBody ?? null
  });
  const body = parseBodyText(response.body);
  if (response.status < 200 || response.status >= 300) {
    throw new Error(errorMessageFromBody(body));
  }
  return body as T;
}

async function requestJson<T>(path: string, options: RequestInit = {}, protectedApi = true): Promise<T> {
  if (protectedApi && isTauriRuntime()) {
    try {
      return await requestViaTauri<T>(path, options);
    } catch (error) {
      throw new Error(humanizeError(error));
    }
  }

  if (protectedApi && !runtimeToken) {
    throw new Error("开发者模式：请填写调试 Token。正式版会自动连接。");
  }

  const headers: HeadersInit = {
    ...(options.body ? { "Content-Type": "application/json" } : {}),
    ...(protectedApi ? { [TOKEN_HEADER]: runtimeToken } : {}),
    ...(options.headers || {})
  };

  try {
    const response = await fetch(`${daemonUrl}${path}`, { ...options, headers });
    const body = await parseBody(response);
    if (!response.ok) {
      throw new Error(errorMessageFromBody(body));
    }
    return body as T;
  } catch (error) {
    throw new Error(humanizeError(error));
  }
}

export async function getHealth(): Promise<HealthStatus> {
  return requestJson<HealthStatus>("/health", {}, false);
}

export async function getAppState(): Promise<AppState> {
  return requestJson<AppState>("/app/state");
}

export async function getRuntimeInfo(): Promise<RuntimeInfo> {
  return requestJson<RuntimeInfo>("/runtime/info");
}

export async function getProviders(): Promise<Provider[]> {
  const body = await requestJson<{ providers: Provider[] }>("/providers");
  return body.providers;
}

export async function openProviderKeyUrl(provider: string): Promise<string> {
  const body = await requestJson<{ key_url: string }>("/providers/open-key-url", {
    method: "POST",
    body: JSON.stringify({ provider, open_browser: true })
  });
  return body.key_url;
}

export async function testProvider(
  provider: string,
  model: string,
  apiKey: string
): Promise<ProviderTestResult> {
  return requestJson<ProviderTestResult>("/providers/test", {
    method: "POST",
    body: JSON.stringify({ provider, model, api_key: apiKey })
  });
}

export async function saveProvider(
  provider: string,
  model: string,
  apiKey: string
): Promise<SaveProviderResult> {
  return requestJson<SaveProviderResult>("/providers/save", {
    method: "POST",
    body: JSON.stringify({ provider, model, api_key: apiKey })
  });
}

export async function sendChatMessage(message: string): Promise<ChatSendResult> {
  return requestJson<ChatSendResult>("/chat/send", {
    method: "POST",
    body: JSON.stringify({ message })
  });
}

export async function getModes(): Promise<ModeProfile[]> {
  const body = await requestJson<{ modes: ModeProfile[] }>("/modes");
  return body.modes;
}

export async function getCurrentMode(): Promise<CurrentMode> {
  return requestJson<CurrentMode>("/modes/current");
}

export async function selectMode(mode: string): Promise<CurrentMode> {
  return requestJson<CurrentMode>("/modes/select", {
    method: "POST",
    body: JSON.stringify({ mode })
  });
}

export async function getWeixinStatus(): Promise<WeixinStatus> {
  return requestJson<WeixinStatus>("/gateway/weixin/status");
}

export async function getWeixinCommands(): Promise<WeixinCommand[]> {
  const body = await requestJson<{ commands: WeixinCommand[] }>("/gateway/weixin/commands");
  return body.commands;
}

export async function getSafetyPolicy(): Promise<SafetyPolicy> {
  const body = await requestJson<{ policy: SafetyPolicy }>("/safety/policy");
  return body.policy;
}

export async function getSafetyApprovals(): Promise<SafetyApprovals> {
  return requestJson<SafetyApprovals>("/safety/approvals");
}

export async function runDoctor(): Promise<DoctorResult> {
  return requestJson<DoctorResult>("/doctor/run");
}

export async function runRepair(checkName = ""): Promise<RepairResult> {
  return requestJson<RepairResult>("/doctor/repair", {
    method: "POST",
    body: JSON.stringify({ check_name: checkName || null })
  });
}
