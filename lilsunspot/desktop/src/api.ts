import type {
  ChatSendResult,
  CurrentMode,
  DoctorResult,
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

const DAEMON_URL = "http://127.0.0.1:8765";
const TOKEN_HEADER = "X-Lilsunspot-Token";

let runtimeToken = "";

type ApiErrorBody = {
  detail?: string;
  message?: string;
  suggestion?: string;
};

export function setRuntimeToken(token: string) {
  runtimeToken = token.trim();
}

export function getDaemonUrl() {
  return DAEMON_URL;
}

export async function readRuntimeToken(): Promise<string | null> {
  try {
    const tauriCore = await import("@tauri-apps/api/core");
    const token = await tauriCore.invoke<string>("read_runtime_token");
    return token.trim() || null;
  } catch {
    return null;
  }
}

function humanizeError(error: unknown): string {
  if (error instanceof Error) {
    if (error.message === "Failed to fetch") {
      return "无法连接 lilsunspotd，请先启动 daemon。";
    }
    return error.message;
  }
  return "请求失败，请稍后再试。";
}

async function parseBody(response: Response): Promise<unknown> {
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

function errorMessageFromBody(body: unknown): string {
  if (typeof body === "string" && body.trim()) {
    return body;
  }
  if (body && typeof body === "object") {
    const value = body as ApiErrorBody;
    return value.detail || value.message || value.suggestion || "请求失败。";
  }
  return "请求失败。";
}

async function requestJson<T>(path: string, options: RequestInit = {}, protectedApi = true): Promise<T> {
  if (protectedApi && !runtimeToken) {
    throw new Error("请先填写 runtime token。");
  }

  const headers: HeadersInit = {
    ...(options.body ? { "Content-Type": "application/json" } : {}),
    ...(protectedApi ? { [TOKEN_HEADER]: runtimeToken } : {}),
    ...(options.headers || {})
  };

  try {
    const response = await fetch(`${DAEMON_URL}${path}`, { ...options, headers });
    const body = await parseBody(response);
    if (!response.ok) {
      throw new Error(errorMessageFromBody(body));
    }
    return body as T;
  } catch (error) {
    throw new Error(humanizeError(error));
  }
}

export async function getHealth(): Promise<{ ok: boolean }> {
  return requestJson<{ ok: boolean }>("/health", {}, false);
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
    body: JSON.stringify({ provider, open_browser: false })
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
