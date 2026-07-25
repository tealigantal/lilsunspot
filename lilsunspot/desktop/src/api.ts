import type {
  AppState,
  AppBootstrapState,
  AppUpdateInstallResult,
  AppUpdateStatus,
  CapabilitiesResult,
  Capability,
  CapabilityGraph,
  CapabilityTestResult,
  ChatSendResult,
  Conversation,
  ConversationMessage,
  ConversationSearchResult,
  ConversationSendResult,
  CurrentMode,
  DaemonConnectStatus,
  DaemonDiscovery,
  DaemonHttpResponse,
  DoctorResult,
  DiagnosticsExportResult,
  DiagnosticsSummary,
  HealthStatus,
  GenerationControl,
  GenerationMode,
  GenerationSelection,
  LilsunspotEvent,
  LocalProviderResetResult,
  ModeProfile,
  ModelCapabilities,
  ModelRuntimeConfig,
  ProductCapability,
  AdvancedConfigExport,
  AdvancedConfigImportResult,
  ProductMemory,
  ProductReminder,
  Provider,
  ProviderTestResult,
  RepairResult,
  RuntimeInfo,
  SafetyApprovals,
  AuditResult,
  AdvancedExtensions,
  SafetyPolicy,
  SafetyApprovalDecisionResult,
  SaveProviderResult,
  ConversationTurnActionResult,
  WeixinCommand,
  WeixinSendApprovalResult,
  WeixinStatus,
  ProductProfile,
  ProductTask,
  ProductTaskRun,
  UiOverview,
  UsageSummary
} from "./types";

const DEFAULT_DAEMON_URL = import.meta.env.VITE_LILSUNSPOT_DAEMON_URL || "http://127.0.0.1:8765";
const TOKEN_HEADER = "X-Lilsunspot-Token";
const CHAT_REQUEST_TIMEOUT_MS = 120_000;
const WEIXIN_REQUEST_TIMEOUT_MS = 12_000;
const WEIXIN_DISCONNECT_TIMEOUT_MS = 5_000;

let runtimeToken = "";
let daemonUrl = DEFAULT_DAEMON_URL;

type ApiErrorBody = {
  detail?: string;
  message?: string;
  suggestion?: string;
  title?: string;
};

type ApiRequestOptions = {
  protectedApi?: boolean;
  timeoutMs?: number;
};

function isTauriRuntime() {
  const tauriWindow = window as Window & {
    __TAURI__?: unknown;
    __TAURI_INTERNALS__?: unknown;
  };
  return (
    typeof window !== "undefined" &&
    ("__TAURI_INTERNALS__" in tauriWindow ||
      "__TAURI__" in tauriWindow ||
      window.location.protocol === "tauri:" ||
      window.location.hostname === "tauri.localhost")
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
  if (typeof error === "string" && error.trim()) {
    return error;
  }
  if (error instanceof Error) {
    if (error.message === "Failed to fetch") {
      return "小黑子本地服务没有响应。请点击“重新检查”。";
    }
    if (error.name === "AbortError") {
      return "请求超时，请稍后再试。";
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

function normalizeApiRequestOptions(value: boolean | ApiRequestOptions): Required<ApiRequestOptions> {
  if (typeof value === "boolean") {
    return { protectedApi: value, timeoutMs: 0 };
  }
  return {
    protectedApi: value.protectedApi ?? true,
    timeoutMs: value.timeoutMs ?? 0
  };
}

function tauriHttpTimeoutMs(timeoutMs: number) {
  if (!timeoutMs) {
    return null;
  }
  return Math.max(1_000, timeoutMs - 500);
}

function withTimeout<T>(promise: Promise<T>, timeoutMs: number, message: string): Promise<T> {
  if (!timeoutMs) {
    return promise;
  }
  return new Promise<T>((resolve, reject) => {
    const timer = window.setTimeout(() => reject(new Error(message)), timeoutMs);
    promise.then(
      (value) => {
        window.clearTimeout(timer);
        resolve(value);
      },
      (error) => {
        window.clearTimeout(timer);
        reject(error);
      }
    );
  });
}

async function requestViaTauri<T>(path: string, options: RequestInit, timeoutMs: number): Promise<T> {
  const method = (options.method || "GET").toUpperCase();
  const rawBody = typeof options.body === "string" ? options.body : undefined;
  const response = await withTimeout(
    invokeTauri<DaemonHttpResponse>("daemon_request", {
      path,
      method,
      body: rawBody ?? null,
      timeoutMs: tauriHttpTimeoutMs(timeoutMs)
    }),
    timeoutMs,
    "本地服务请求超时，请稍后再试。"
  );
  const body = parseBodyText(response.body);
  if (response.status < 200 || response.status >= 300) {
    throw new Error(errorMessageFromBody(body));
  }
  return body as T;
}

async function requestJson<T>(
  path: string,
  options: RequestInit = {},
  requestOptions: boolean | ApiRequestOptions = true
): Promise<T> {
  const { protectedApi, timeoutMs } = normalizeApiRequestOptions(requestOptions);
  if (isTauriRuntime()) {
    try {
      return await requestViaTauri<T>(path, options, timeoutMs);
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

  const controller = timeoutMs ? new AbortController() : null;
  let timeoutId: number | null = null;
  let timedOut = false;
  const externalSignal = options.signal;
  const abortFromExternal = () => controller?.abort();
  try {
    if (controller && externalSignal) {
      if (externalSignal.aborted) {
        controller.abort();
      } else {
        externalSignal.addEventListener("abort", abortFromExternal, { once: true });
      }
    }
    if (controller) {
      timeoutId = window.setTimeout(() => {
        timedOut = true;
        controller.abort();
      }, timeoutMs);
    }
    const response = await fetch(`${daemonUrl}${path}`, {
      ...options,
      headers,
      signal: controller?.signal ?? options.signal
    });
    const body = await parseBody(response);
    if (!response.ok) {
      throw new Error(errorMessageFromBody(body));
    }
    return body as T;
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError") {
      throw new Error(timedOut ? "请求超时，请稍后再试。" : humanizeError(error));
    }
    throw new Error(humanizeError(error));
  } finally {
    if (timeoutId !== null) {
      window.clearTimeout(timeoutId);
    }
    if (controller && externalSignal) {
      externalSignal.removeEventListener("abort", abortFromExternal);
    }
  }
}

export async function getHealth(): Promise<HealthStatus> {
  return requestJson<HealthStatus>("/health", {}, false);
}

export async function getAppState(): Promise<AppState> {
  return requestJson<AppState>("/app/state");
}

export async function getAppBootstrap(): Promise<AppBootstrapState> {
  return requestJson<AppBootstrapState>("/app/bootstrap");
}

export async function getUiOverview(): Promise<UiOverview> {
  return requestJson<UiOverview>("/ui/overview");
}

export async function getRuntimeInfo(): Promise<RuntimeInfo> {
  return requestJson<RuntimeInfo>("/runtime/info");
}

export async function getProviders(): Promise<Provider[]> {
  const body = await requestJson<{ providers: Provider[] }>("/providers");
  return body.providers;
}

export async function getProviderCapabilities(): Promise<ModelCapabilities> {
  return requestJson<ModelCapabilities>("/providers/capabilities");
}

export async function getCapabilityGraph(): Promise<CapabilityGraph> {
  return requestJson<CapabilityGraph>("/capability-graph");
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
  apiKey: string,
  baseUrlOverride = ""
): Promise<ProviderTestResult> {
  return requestJson<ProviderTestResult>("/providers/test", {
    method: "POST",
    body: JSON.stringify({ provider, model, api_key: apiKey, base_url_override: baseUrlOverride })
  });
}

export async function saveProvider(
  provider: string,
  model: string,
  apiKey: string,
  baseUrlOverride = ""
): Promise<SaveProviderResult> {
  return requestJson<SaveProviderResult>("/providers/save", {
    method: "POST",
    body: JSON.stringify({ provider, model, api_key: apiKey, base_url_override: baseUrlOverride })
  });
}

export async function resetLocalProviderConfig(): Promise<LocalProviderResetResult> {
  return requestJson<LocalProviderResetResult>("/providers/reset-local", {
    method: "POST"
  });
}

export async function getModelRuntimeConfig(): Promise<ModelRuntimeConfig> {
  return requestJson<ModelRuntimeConfig>("/models/runtime");
}

export async function saveAuxiliaryModel(payload: {
  task: string;
  provider: string;
  model: string;
  base_url?: string;
  api_key?: string;
}): Promise<ModelRuntimeConfig> {
  const body = await requestJson<{ ok: boolean; models: ModelRuntimeConfig }>("/models/auxiliary", {
    method: "POST",
    body: JSON.stringify(payload)
  });
  return body.models;
}

export async function getCapabilities(): Promise<CapabilitiesResult> {
  return requestJson<CapabilitiesResult>("/capabilities");
}

export async function patchCapability(capabilityId: string, enabled: boolean): Promise<Capability> {
  const body = await requestJson<{ ok: boolean; capability: Capability }>(`/capabilities/${encodeURIComponent(capabilityId)}`, {
    method: "PATCH",
    body: JSON.stringify({ enabled })
  });
  return body.capability;
}

export async function testCapability(capabilityId: string): Promise<CapabilityTestResult> {
  return requestJson<CapabilityTestResult>(`/capabilities/${encodeURIComponent(capabilityId)}/test`, {
    method: "POST"
  });
}

export async function sendChatMessage(message: string): Promise<ChatSendResult> {
  return requestJson<ChatSendResult>("/chat/send", {
    method: "POST",
    body: JSON.stringify({ message })
  }, { timeoutMs: CHAT_REQUEST_TIMEOUT_MS });
}

export async function getConversations(includeArchived = false): Promise<Conversation[]> {
  const params = new URLSearchParams();
  if (includeArchived) {
    params.set("include_archived", "true");
  }
  const suffix = params.toString() ? `?${params.toString()}` : "";
  const body = await requestJson<{ conversations: Conversation[] }>(`/conversations${suffix}`);
  return body.conversations;
}

export async function searchConversations(query: string, includeArchived = false): Promise<ConversationSearchResult[]> {
  const body = await requestJson<{ results: ConversationSearchResult[] }>("/conversations/search", {
    method: "POST",
    body: JSON.stringify({ query, include_archived: includeArchived, limit: 20 })
  });
  return body.results;
}

export async function searchSessions(query: string, includeArchived = false): Promise<ConversationSearchResult[]> {
  const body = await requestJson<{ results: ConversationSearchResult[] }>("/sessions/search", {
    method: "POST",
    body: JSON.stringify({ query, include_archived: includeArchived, limit: 50 })
  });
  return body.results;
}

export async function createConversation(payload: {
  title?: string;
  kind?: string;
  metadata?: Record<string, unknown>;
} = {}): Promise<Conversation> {
  const body = await requestJson<{ conversation: Conversation }>("/conversations", {
    method: "POST",
    body: JSON.stringify(payload)
  });
  return body.conversation;
}

export async function updateConversation(
  conversationId: string,
  payload: { title?: string; archived?: boolean; weixin_route_active?: boolean }
): Promise<Conversation> {
  const body = await requestJson<{ conversation: Conversation }>(`/conversations/${encodeURIComponent(conversationId)}`, {
    method: "PATCH",
    body: JSON.stringify(payload)
  });
  return body.conversation;
}

export async function deleteConversation(conversationId: string): Promise<boolean> {
  const body = await requestJson<{ ok: boolean }>(`/conversations/${encodeURIComponent(conversationId)}`, {
    method: "DELETE"
  });
  return body.ok;
}

export async function getConversationMessages(conversationId = "personal", afterId = "", limit = 80): Promise<ConversationMessage[]> {
  const params = new URLSearchParams();
  if (afterId) {
    params.set("after_id", afterId);
  }
  params.set("limit", String(limit));
  const body = await requestJson<{ messages: ConversationMessage[] }>(
    `/conversations/${encodeURIComponent(conversationId)}/messages?${params.toString()}`
  );
  return body.messages;
}

type ConversationUploadAttachment = {
  file_name: string;
  mime_type: string;
  data_base64: string;
};

async function fileToUploadAttachment(file: File): Promise<ConversationUploadAttachment> {
  const dataUrl = await new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ""));
    reader.onerror = () => reject(new Error("附件读取失败。"));
    reader.readAsDataURL(file);
  });
  const commaIndex = dataUrl.indexOf(",");
  return {
    file_name: file.name,
    mime_type: file.type || "application/octet-stream",
    data_base64: commaIndex >= 0 ? dataUrl.slice(commaIndex + 1) : dataUrl
  };
}

export async function sendConversationMessage(
  conversationId: string,
  message: string,
  attachments: File[] = [],
  generationOverride?: GenerationSelection | null
): Promise<ConversationSendResult> {
  const payloadAttachments = await Promise.all(attachments.map((file) => fileToUploadAttachment(file)));
  return requestJson<ConversationSendResult>(`/conversations/${encodeURIComponent(conversationId)}/messages`, {
    method: "POST",
    body: JSON.stringify({
      message,
      attachments: payloadAttachments,
      ...(generationOverride ? { generation_override: generationOverride } : {})
    })
  }, { timeoutMs: CHAT_REQUEST_TIMEOUT_MS });
}

export async function stopConversationTurn(conversationId: string, message = ""): Promise<ConversationTurnActionResult> {
  return requestJson<ConversationTurnActionResult>(`/conversations/${encodeURIComponent(conversationId)}/turns/stop`, {
    method: "POST",
    body: JSON.stringify({ message })
  });
}

export async function retryConversationTurn(conversationId: string): Promise<ConversationTurnActionResult> {
  return requestJson<ConversationTurnActionResult>(`/conversations/${encodeURIComponent(conversationId)}/turns/retry`, {
    method: "POST"
  }, { timeoutMs: CHAT_REQUEST_TIMEOUT_MS });
}

export async function undoConversationTurn(conversationId: string): Promise<ConversationTurnActionResult> {
  return requestJson<ConversationTurnActionResult>(`/conversations/${encodeURIComponent(conversationId)}/turns/undo`, {
    method: "POST"
  });
}

export async function branchConversationTurn(conversationId: string, title = ""): Promise<ConversationTurnActionResult> {
  return requestJson<ConversationTurnActionResult>(`/conversations/${encodeURIComponent(conversationId)}/turns/branch`, {
    method: "POST",
    body: JSON.stringify({ title: title || null })
  });
}

export async function saveConversationSummary(conversationId: string): Promise<ConversationTurnActionResult> {
  return requestJson<ConversationTurnActionResult>(`/conversations/${encodeURIComponent(conversationId)}/turns/save-summary`, {
    method: "POST"
  });
}

export async function subscribeDaemonEvents(): Promise<boolean> {
  if (!isTauriRuntime()) {
    return false;
  }
  return invokeTauri<boolean>("subscribe_events");
}

export async function listenDaemonEvents(onEvent: (event: LilsunspotEvent) => void): Promise<() => void> {
  if (!isTauriRuntime()) {
    return () => undefined;
  }
  const tauriEvent = await import("@tauri-apps/api/event");
  return tauriEvent.listen<LilsunspotEvent>("lilsunspot:event", (event) => onEvent(event.payload));
}

export async function openAttachment(attachmentId: string): Promise<boolean> {
  if (!isTauriRuntime()) {
    throw new Error("正式版会从本机安全目录打开附件。");
  }
  return invokeTauri<boolean>("open_attachment", { attachmentId });
}

export async function checkUpdate(): Promise<AppUpdateStatus> {
  if (!isTauriRuntime()) {
    return {
      state: "unavailable",
      update: null,
      message: "正式桌面版会从小黑子的更新源检查版本。"
    };
  }
  try {
    return await invokeTauri<AppUpdateStatus>("check_update");
  } catch (error) {
    return {
      state: "failed",
      update: null,
      message: humanizeError(error)
    };
  }
}

export async function downloadAndInstallUpdate(): Promise<AppUpdateInstallResult> {
  if (!isTauriRuntime()) {
    throw new Error("正式桌面版才能安装更新。");
  }
  try {
    return await invokeTauri<AppUpdateInstallResult>("download_and_install_update");
  } catch (error) {
    throw new Error(humanizeError(error));
  }
}

export async function dismissUpdate(version: string): Promise<void> {
  if (!isTauriRuntime()) {
    return;
  }
  try {
    await invokeTauri<void>("dismiss_update_version", { version });
  } catch (error) {
    throw new Error(humanizeError(error));
  }
}

export async function getModes(): Promise<ModeProfile[]> {
  const body = await requestJson<{ modes: ModeProfile[] }>("/modes");
  return body.modes;
}

export async function getCurrentMode(conversationId = ""): Promise<CurrentMode> {
  const params = new URLSearchParams();
  if (conversationId) {
    params.set("conversation_id", conversationId);
  }
  const suffix = params.toString() ? `?${params.toString()}` : "";
  return requestJson<CurrentMode>(`/modes/current${suffix}`);
}

export async function selectMode(
  mode: string,
  sliders?: Pick<ModeProfile, "style_axis" | "detail_level" | "autonomy_level">,
  options?: { conversationId?: string; scope?: "global" | "conversation" | "turn" }
): Promise<CurrentMode> {
  const conversationId = options?.conversationId || "";
  return requestJson<CurrentMode>("/modes/select", {
    method: "POST",
    body: JSON.stringify({
      mode,
      ...(sliders || {}),
      ...(conversationId ? { conversation_id: conversationId } : {}),
      ...(options?.scope ? { scope: options.scope } : {})
    })
  });
}

export async function getGenerationModes(): Promise<GenerationMode[]> {
  const body = await requestJson<{ modes: GenerationMode[] }>("/generation/modes");
  return body.modes;
}

export async function getCurrentGenerationControl(conversationId = ""): Promise<GenerationControl> {
  const params = new URLSearchParams();
  if (conversationId) {
    params.set("conversation_id", conversationId);
  }
  const suffix = params.toString() ? `?${params.toString()}` : "";
  return requestJson<GenerationControl>(`/generation/current${suffix}`);
}

export async function selectGenerationControl(
  selection: GenerationSelection,
  options: { conversationId?: string; scope: "global" | "conversation" | "turn" }
): Promise<GenerationControl> {
  return requestJson<GenerationControl>("/generation/select", {
    method: "POST",
    body: JSON.stringify({
      ...selection,
      scope: options.scope,
      ...(options.conversationId ? { conversation_id: options.conversationId } : {})
    })
  });
}

export async function resetGenerationControl(
  options: { conversationId?: string; scope: "global" | "conversation" }
): Promise<GenerationControl> {
  return requestJson<GenerationControl>("/generation/reset", {
    method: "POST",
    body: JSON.stringify({
      scope: options.scope,
      ...(options.conversationId ? { conversation_id: options.conversationId } : {})
    })
  });
}

export async function getWeixinStatus(): Promise<WeixinStatus> {
  return requestJson<WeixinStatus>("/gateway/weixin/status", {}, { timeoutMs: WEIXIN_REQUEST_TIMEOUT_MS });
}

export async function getWeixinCommands(): Promise<WeixinCommand[]> {
  const body = await requestJson<{ commands: WeixinCommand[] }>("/gateway/weixin/commands");
  return body.commands;
}

export async function startWeixinLogin(): Promise<WeixinStatus> {
  return requestJson<WeixinStatus>("/gateway/weixin/login/start", {
    method: "POST"
  }, { timeoutMs: WEIXIN_REQUEST_TIMEOUT_MS });
}

export async function getWeixinLoginStatus(): Promise<WeixinStatus> {
  return requestJson<WeixinStatus>("/gateway/weixin/login/status", {}, { timeoutMs: WEIXIN_REQUEST_TIMEOUT_MS });
}

export async function disconnectWeixin(): Promise<WeixinStatus> {
  return requestJson<WeixinStatus>("/gateway/weixin/disconnect", {
    method: "POST"
  }, { timeoutMs: WEIXIN_DISCONNECT_TIMEOUT_MS });
}

export async function sendWeixinMessage(
  recipient: string,
  message: string,
  attachmentIds: string[] = []
): Promise<WeixinSendApprovalResult> {
  return requestJson<WeixinSendApprovalResult>("/gateway/weixin/send", {
    method: "POST",
    body: JSON.stringify({ recipient, message, attachment_ids: attachmentIds })
  });
}

export async function getSafetyApprovals(): Promise<SafetyApprovals> {
  return requestJson<SafetyApprovals>("/safety/approvals");
}

export async function getSafetyAudit(limit = 50): Promise<AuditResult> {
  const params = new URLSearchParams({ limit: String(limit) });
  return requestJson<AuditResult>(`/safety/audit?${params.toString()}`);
}

export async function getSafetyPolicy(): Promise<SafetyPolicy> {
  const body = await requestJson<{ policy: SafetyPolicy }>("/safety/policy");
  return body.policy;
}

export async function decideSafetyApproval(
  approvalId: string,
  decision: "approved" | "rejected"
): Promise<SafetyApprovalDecisionResult> {
  return requestJson<SafetyApprovalDecisionResult>(`/safety/approvals/${encodeURIComponent(approvalId)}/decide`, {
    method: "POST",
    body: JSON.stringify({ decision })
  });
}

export async function getDiagnosticsSummary(): Promise<DiagnosticsSummary> {
  return requestJson<DiagnosticsSummary>("/diagnostics/summary");
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

export async function getReminders(): Promise<ProductReminder[]> {
  const body = await requestJson<{ reminders: ProductReminder[] }>("/reminders");
  return body.reminders;
}

export async function createReminder(title: string, prompt: string, dueAt = ""): Promise<ProductReminder> {
  const body = await requestJson<{ reminder: ProductReminder }>("/reminders", {
    method: "POST",
    body: JSON.stringify({ title, prompt, due_at: dueAt })
  });
  return body.reminder;
}

export async function updateReminder(
  reminderId: string,
  payload: { enabled?: boolean; completed?: boolean }
): Promise<ProductReminder> {
  const body = await requestJson<{ reminder: ProductReminder }>(`/reminders/${encodeURIComponent(reminderId)}`, {
    method: "PATCH",
    body: JSON.stringify(payload)
  });
  return body.reminder;
}

export async function deleteReminder(reminderId: string): Promise<boolean> {
  const body = await requestJson<{ ok: boolean }>(`/reminders/${encodeURIComponent(reminderId)}`, {
    method: "DELETE"
  });
  return body.ok;
}

export async function getTasks(): Promise<ProductTask[]> {
  const body = await requestJson<{ tasks: ProductTask[] }>("/tasks");
  return body.tasks;
}

export async function createTask(title: string, prompt: string, dueAt = "", kind = "reminder", schedule = "once"): Promise<ProductTask> {
  const body = await requestJson<{ task: ProductTask }>("/tasks", {
    method: "POST",
    body: JSON.stringify({ title, prompt, due_at: dueAt, kind, schedule })
  });
  return body.task;
}

export async function updateTask(
  taskId: string,
  payload: { title?: string; prompt?: string; due_at?: string; kind?: string; schedule?: string; enabled?: boolean; completed?: boolean }
): Promise<ProductTask> {
  const body = await requestJson<{ task: ProductTask }>(`/tasks/${encodeURIComponent(taskId)}`, {
    method: "PATCH",
    body: JSON.stringify(payload)
  });
  return body.task;
}

export async function runTask(taskId: string): Promise<{ task: ProductTask; run: ProductTaskRun }> {
  return requestJson<{ task: ProductTask; run: ProductTaskRun }>(`/tasks/${encodeURIComponent(taskId)}/run`, {
    method: "POST"
  });
}

export async function deleteTask(taskId: string): Promise<boolean> {
  const body = await requestJson<{ ok: boolean }>(`/tasks/${encodeURIComponent(taskId)}`, {
    method: "DELETE"
  });
  return body.ok;
}

export async function getMemories(): Promise<ProductMemory[]> {
  const body = await requestJson<{ memories: ProductMemory[] }>("/memory");
  return body.memories;
}

export async function createMemory(text: string): Promise<ProductMemory> {
  const body = await requestJson<{ memory: ProductMemory }>("/memory", {
    method: "POST",
    body: JSON.stringify({ text, source: "manual" })
  });
  return body.memory;
}

export async function updateMemory(memoryId: string, enabled: boolean): Promise<ProductMemory> {
  const body = await requestJson<{ memory: ProductMemory }>(`/memory/${encodeURIComponent(memoryId)}`, {
    method: "PATCH",
    body: JSON.stringify({ enabled })
  });
  return body.memory;
}

export async function deleteMemory(memoryId: string): Promise<boolean> {
  const body = await requestJson<{ ok: boolean }>(`/memory/${encodeURIComponent(memoryId)}`, {
    method: "DELETE"
  });
  return body.ok;
}

export async function getProfiles(): Promise<ProductProfile[]> {
  const body = await requestJson<{ profiles: ProductProfile[] }>("/profiles");
  return body.profiles;
}

export async function createProfile(name: string, instructions: string): Promise<ProductProfile> {
  const body = await requestJson<{ profile: ProductProfile }>("/profiles", {
    method: "POST",
    body: JSON.stringify({ name, instructions })
  });
  return body.profile;
}

export async function deleteProfile(profileId: string): Promise<boolean> {
  const body = await requestJson<{ ok: boolean }>(`/profiles/${encodeURIComponent(profileId)}`, {
    method: "DELETE"
  });
  return body.ok;
}

export async function getProductCapabilities(): Promise<ProductCapability[]> {
  const body = await requestJson<{ capabilities: ProductCapability[] }>("/product/capabilities");
  return body.capabilities;
}

export async function updateProductCapability(capabilityId: string, enabled: boolean): Promise<ProductCapability> {
  const body = await requestJson<{ capability: ProductCapability }>(`/product/capabilities/${encodeURIComponent(capabilityId)}`, {
    method: "PATCH",
    body: JSON.stringify({ enabled })
  });
  return body.capability;
}

export async function getUsageSummary(): Promise<UsageSummary> {
  return requestJson<UsageSummary>("/usage/summary");
}

export async function getAdvancedExtensions(): Promise<AdvancedExtensions> {
  return requestJson<AdvancedExtensions>("/advanced/extensions");
}

export async function exportAdvancedConfig(): Promise<AdvancedConfigExport> {
  return requestJson<AdvancedConfigExport>("/advanced/config/export");
}

export async function importAdvancedConfig(config: Record<string, unknown>): Promise<AdvancedConfigImportResult> {
  return requestJson<AdvancedConfigImportResult>("/advanced/config/import", {
    method: "POST",
    body: JSON.stringify({ config })
  });
}

export async function exportDiagnostics(): Promise<DiagnosticsExportResult> {
  return requestJson<DiagnosticsExportResult>("/doctor/diagnostics/export", {
    method: "POST"
  });
}
